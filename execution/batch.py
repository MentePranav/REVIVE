"""
Batch Execution Runner for REVIVE Controlled Recovery Pipeline.
Processes large datasets, tracking state context, financial yield, and safety metrics.
"""

from typing import Dict, List, Optional, Tuple, Union
from agent.models import ReviveRecommendation
from evaluation.pipeline import DatasetLoader
from execution.models import (
    ActionExecutionStats,
    BatchExecutionSummary,
    ExecutionLifecycleTrace,
    ExecutionStatus,
    SimulatedRecoveryOutcome,
)
from execution.orchestrator import ReviveOrchestrator
from policy.config import PolicyConfig
from policy.models import PolicyDecisionType
from policy.state_context import CustomerStateContext, PaymentStateContext
from simulator.enums import PaymentStatus, RecoveryAction
from simulator.ground_truth_schema import GroundTruthRecord
from simulator.public_schema import AbandonedCheckout, Customer, Transaction


class BatchExecutionRunner:
    """Executes REVIVE end-to-end recovery across transaction datasets."""

    def __init__(self, policy_config: Optional[PolicyConfig] = None):
        self.orchestrator = ReviveOrchestrator(policy_config)

    def run_batch(
        self,
        events: List[Union[Transaction, AbandonedCheckout]],
        customers_by_id: Dict[str, Customer],
        ground_truth_map: Optional[Dict[str, GroundTruthRecord]] = None,
        total_transactions: int = 10000
    ) -> Tuple[List[ExecutionLifecycleTrace], BatchExecutionSummary]:
        traces: List[ExecutionLifecycleTrace] = []
        payment_states: Dict[str, PaymentStateContext] = {}
        customer_states: Dict[str, CustomerStateContext] = {}

        # Metric accumulators
        policy_auth = 0
        policy_hr = 0
        policy_deny = 0
        policy_no_action = 0
        actions_exec = 0
        actions_blocked = 0
        duplicates = 0
        success_recoveries = 0

        rev_at_risk = 0.0
        natural_rev = 0.0
        total_recovered = 0.0

        action_stats: Dict[str, ActionExecutionStats] = {
            act.value: ActionExecutionStats(action=act.value)
            for act in RecoveryAction
        }

        safety_counts: Dict[str, int] = {
            "unauthorized_attempts_blocked": 0,
            "resolved_payment_attempts_blocked": 0,
            "attempt_cap_violations_blocked": 0,
            "contact_limit_violations_blocked": 0,
            "cooldown_violations_blocked": 0,
            "duplicate_executions_prevented": 0,
            "human_review_cases": 0,
            "policy_denials": 0,
        }

        # Sort strictly chronologically (no look-ahead)
        sorted_events = sorted(events, key=lambda e: e.created_at)

        for event in sorted_events:
            # Skip successful transactions
            if isinstance(event, Transaction) and event.status == PaymentStatus.SUCCESS:
                continue

            event_id = event.transaction_id if isinstance(event, Transaction) else event.checkout_id
            payment_id = f"pay_{event_id.replace('txn_', '').replace('chk_', '')}"
            customer_id = event.customer_id
            amount = event.amount

            rev_at_risk += amount

            # Retrieve state contexts
            p_state = payment_states.setdefault(payment_id, PaymentStateContext(payment_id=payment_id, customer_id=customer_id))
            c_state = customer_states.setdefault(customer_id, CustomerStateContext(customer_id=customer_id))

            gt = ground_truth_map.get(event_id) if ground_truth_map else None

            # Track natural baseline recovery
            if gt and gt.is_already_resolved:
                natural_rev += amount

            # Execute full pipeline
            trace = self.orchestrator.process_event(
                event=event,
                customer=customers_by_id.get(customer_id),
                payment_state=p_state,
                customer_state=c_state,
                ground_truth=gt
            )
            traces.append(trace)

            rec_act = trace.recommendation.recommended_action.value
            action_stats[rec_act].recommended_count += 1

            # Update Policy Metrics
            p_dec = trace.policy_decision
            if p_dec.decision == PolicyDecisionType.ALLOW:
                policy_auth += 1
                action_stats[rec_act].authorized_count += 1
            elif p_dec.decision == PolicyDecisionType.HUMAN_REVIEW:
                policy_hr += 1
                safety_counts["human_review_cases"] += 1
            elif p_dec.decision == PolicyDecisionType.NO_ACTION:
                policy_no_action += 1
            elif p_dec.decision == PolicyDecisionType.DENY:
                policy_deny += 1
                safety_counts["policy_denials"] += 1

            # Update Execution Metrics
            ex_res = trace.execution_result
            if ex_res.execution_status == ExecutionStatus.EXECUTED:
                actions_exec += 1
                action_stats[rec_act].executed_count += 1

                # Update state counts
                p_state.automated_attempt_count += 1
                if ex_res.authorized_action == RecoveryAction.RETRY:
                    p_state.retry_attempt_count += 1
                if ex_res.authorized_action in (RecoveryAction.REMINDER, RecoveryAction.PAYMENT_LINK):
                    c_state.contact_actions_count += 1

                p_state.last_action_timestamp = ex_res.executed_at
                p_state.last_action_type = ex_res.authorized_action

                # Check recovery outcome
                if ex_res.recovery_outcome in (SimulatedRecoveryOutcome.RECOVERED, SimulatedRecoveryOutcome.NATURAL_RECOVERY):
                    success_recoveries += 1
                    total_recovered += ex_res.recovered_amount
                    action_stats[rec_act].recovered_count += 1
                    action_stats[rec_act].recovered_revenue += ex_res.recovered_amount
                    p_state.is_already_resolved = True
                    p_state.current_status = PaymentStatus.SUCCESS

            elif ex_res.execution_status == ExecutionStatus.BLOCKED:
                actions_blocked += 1
                action_stats[rec_act].blocked_count += 1
                if "MISSING_AUTHORIZATION" in ex_res.execution_reason:
                    safety_counts["unauthorized_attempts_blocked"] += 1
                elif "PAYMENT_STATE_CHANGED" in ex_res.execution_reason:
                    safety_counts["resolved_payment_attempts_blocked"] += 1
                elif "MAX_ATTEMPTS" in ex_res.execution_reason:
                    safety_counts["attempt_cap_violations_blocked"] += 1
                elif "CONTACT_LIMIT" in ex_res.execution_reason:
                    safety_counts["contact_limit_violations_blocked"] += 1
                elif "COOLDOWN" in ex_res.execution_reason:
                    safety_counts["cooldown_violations_blocked"] += 1

            elif ex_res.execution_status == ExecutionStatus.DUPLICATE:
                duplicates += 1
                safety_counts["duplicate_executions_prevented"] += 1

        # Calculate Rates & Financials
        n_ops = len(traces)
        rec_rate = (success_recoveries / n_ops) if n_ops > 0 else 0.0
        intervention_success = (success_recoveries / actions_exec) if actions_exec > 0 else 0.0
        incremental_rev = max(0.0, total_recovered - natural_rev)

        for act_name, st in action_stats.items():
            st.recovery_rate = round((st.recovered_count / st.recommended_count) if st.recommended_count > 0 else 0.0, 4)
            st.intervention_success_rate = round((st.recovered_count / st.executed_count) if st.executed_count > 0 else 0.0, 4)
            st.recovered_revenue = round(st.recovered_revenue, 2)

        summary = BatchExecutionSummary(
            total_transactions=total_transactions,
            total_failed_opportunities=n_ops,
            recommendations_count=n_ops,
            policy_authorized_count=policy_auth,
            policy_human_review_count=policy_hr,
            policy_denied_count=policy_deny,
            policy_no_action_count=policy_no_action,
            actions_executed_count=actions_exec,
            actions_blocked_count=actions_blocked,
            duplicate_attempts_prevented=duplicates,
            successful_recoveries=success_recoveries,
            total_revenue_at_risk=round(rev_at_risk, 2),
            natural_recovery_revenue=round(natural_rev, 2),
            total_recovered_revenue=round(total_recovered, 2),
            incremental_recovered_revenue=round(incremental_rev, 2),
            overall_recovery_rate=round(rec_rate, 4),
            intervention_success_rate=round(intervention_success, 4),
            action_breakdown=action_stats,
            safety_metrics=safety_counts,
            executor_version="1.0.0"
        )

        return traces, summary
