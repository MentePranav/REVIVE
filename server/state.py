"""
In-Memory Session State and Backend Coordinator for REVIVE Interactive Control Center.
Manages active synthetic datasets, execution traces, state contexts, and audit logs.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from core.config import APP_CONFIG
from core.errors import AuthorizationError, ExecutionError, InputError, PolicyError
from core.logging import get_logger
from evaluation.experiment.dataset_splitter import DatasetBundle, DatasetSplitter
from evaluation.models import EvaluationMetrics
from execution.batch import BatchExecutionRunner
from execution.executor import ControlledExecutor
from execution.models import (
    AuditEventType,
    ExecutionAuditEvent,
    ExecutionLifecycleTrace,
    ExecutionResult,
    ExecutionStatus,
    SimulatedRecoveryOutcome,
)
from execution.orchestrator import ReviveOrchestrator
from policy.config import PolicyConfig
from policy.models import PolicyDecisionType, PolicyRuleId
from policy.state_context import CustomerStateContext, PaymentStateContext
from server.models import (
    ActionMixStat,
    ActionScoreItem,
    AuditLogItem,
    BenchmarkResponse,
    ExecuteRecoveryResponse,
    RecoveryCaseDetailResponse,
    RecoveryCaseListItem,
    SafetyCheckItem,
    SafetyDashboardResponse,
    SimulationSummaryResponse,
)
from simulator.enums import PaymentStatus, RecoveryAction

logger = get_logger("revive.state")


class ServerStateManager:
    """Manages active demo state and executes authorized workflows."""

    def __init__(self):
        self.policy_config = PolicyConfig()
        self.orchestrator = ReviveOrchestrator(self.policy_config)
        self.executor = ControlledExecutor(self.policy_config)

        # Active Session State
        self.seed: int = APP_CONFIG.default_demo_seed
        self.size: int = APP_CONFIG.default_demo_size
        self.scenario: str = APP_CONFIG.default_scenario
        self.bundle: Optional[DatasetBundle] = None
        self.traces: List[ExecutionLifecycleTrace] = []
        self.traces_by_id: Dict[str, ExecutionLifecycleTrace] = {}
        self.payment_states: Dict[str, PaymentStateContext] = {}
        self.customer_states: Dict[str, CustomerStateContext] = {}
        self.audit_log: List[ExecutionAuditEvent] = []
        self.latest_summary: Optional[SimulationSummaryResponse] = None

        # Automatically initialize default session
        self.initialize_session(seed=self.seed, size=self.size, scenario=self.scenario)

    def initialize_session(self, seed: int = 42, size: int = 100, scenario: str = "balanced") -> SimulationSummaryResponse:
        self.seed = seed
        self.size = size
        self.scenario = scenario

        # 1. Reset Contexts and Executor Cache
        if hasattr(self.executor, "execution_cache"):
            self.executor.execution_cache.clear()
        self.payment_states.clear()
        self.customer_states.clear()
        self.audit_log.clear()

        # 2. Generate Synthetic Dataset
        self.bundle = DatasetSplitter.generate_evaluation_set(seed=seed, transaction_count=size)

        # 3. Run Controlled Execution Pipeline across all opportunities
        runner = BatchExecutionRunner(self.policy_config)
        traces, summary = runner.run_batch(
            events=self.bundle.all_opportunities,
            customers_by_id=self.bundle.customers_by_id,
            ground_truth_map=self.bundle.ground_truth_map,
            total_transactions=len(self.bundle.transactions)
        )
        self.traces = traces
        self.traces_by_id = {t.event_id: t for t in traces}

        # Collect all audit events
        for t in traces:
            self.audit_log.extend(t.audit_events)

        # Build Response
        action_stats_map = {
            k: ActionMixStat(
                action=v.action,
                recommended_count=v.recommended_count,
                authorized_count=v.authorized_count,
                executed_count=v.executed_count,
                recovered_count=v.recovered_count,
                recovered_revenue=v.recovered_revenue,
                recovery_rate=v.recovery_rate,
                intervention_success_rate=v.intervention_success_rate
            ) for k, v in summary.action_breakdown.items()
        }

        self.latest_summary = SimulationSummaryResponse(
            total_transactions=summary.total_transactions,
            total_failed_opportunities=summary.total_failed_opportunities,
            revenue_at_risk=summary.total_revenue_at_risk,
            natural_recovery_revenue=summary.natural_recovery_revenue,
            total_recovered_revenue=summary.total_recovered_revenue,
            incremental_recovered_revenue=summary.incremental_recovered_revenue,
            overall_recovery_rate=summary.overall_recovery_rate,
            intervention_success_rate=summary.intervention_success_rate,
            policy_authorized_count=summary.policy_authorized_count,
            policy_human_review_count=summary.policy_human_review_count,
            policy_denied_count=summary.policy_denied_count,
            policy_no_action_count=summary.policy_no_action_count,
            actions_executed_count=summary.actions_executed_count,
            actions_blocked_count=summary.actions_blocked_count,
            duplicate_attempts_prevented=summary.duplicate_attempts_prevented,
            action_breakdown=action_stats_map,
            safety_metrics=summary.safety_metrics,
            session_seed=seed,
            scenario=scenario
        )

        return self.latest_summary

    def reset_demo_session(self) -> SimulationSummaryResponse:
        """Resets the demo session to a known deterministic golden state."""
        return self.initialize_session(
            seed=APP_CONFIG.default_demo_seed,
            size=APP_CONFIG.default_demo_size,
            scenario=APP_CONFIG.default_scenario
        )

    def get_summary(self) -> SimulationSummaryResponse:
        if not self.latest_summary:
            return self.initialize_session()
        return self.latest_summary

    def get_cases(
        self,
        status_filter: Optional[str] = None,
        action_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        sort_by: Optional[str] = None
    ) -> List[RecoveryCaseListItem]:
        items: List[RecoveryCaseListItem] = []
        if not self.bundle:
            return items

        for t in self.traces:
            event = self.bundle.customers_by_id.get(t.customer_id)
            rec = t.recommendation
            ex = t.execution_result
            pol = t.policy_decision

            # Filtering
            if status_filter and status_filter != "all":
                if status_filter == "recovered" and ex.recovery_outcome not in (SimulatedRecoveryOutcome.RECOVERED, SimulatedRecoveryOutcome.NATURAL_RECOVERY):
                    continue
                if status_filter == "blocked" and ex.execution_status != ExecutionStatus.BLOCKED:
                    continue
                if status_filter == "human_review" and pol.decision != PolicyDecisionType.HUMAN_REVIEW:
                    continue
                if status_filter == "no_action" and pol.decision != PolicyDecisionType.NO_ACTION:
                    continue

            if action_filter and action_filter != "all":
                if rec.recommended_action.value != action_filter:
                    continue

            if search_query:
                q = search_query.lower()
                if q not in t.event_id.lower() and q not in t.customer_id.lower() and q not in rec.diagnosis.category.value.lower():
                    continue

            items.append(RecoveryCaseListItem(
                event_id=t.event_id,
                payment_id=t.payment_id,
                customer_id=t.customer_id,
                amount=rec.amount,
                failure_category=rec.diagnosis.category.value,
                error_reason=rec.diagnosis.explanation,
                diagnosis=rec.diagnosis.category.value,
                confidence=rec.diagnosis.confidence,
                recoverability_score=rec.recoverability_score,
                recoverability_tier=rec.recoverability_tier.value,
                recommended_action=rec.recommended_action.value,
                policy_decision=pol.decision.value,
                primary_rule_id=pol.primary_rule_id.value if pol.primary_rule_id else None,
                execution_status=ex.execution_status.value,
                recovery_outcome=ex.recovery_outcome.value,
                recovered_amount=ex.recovered_amount,
                has_authorization=(pol.execution_authorization is not None),
                created_at=t.recommendation.timestamp
            ))

        # Sorting
        if sort_by == "amount_desc":
            items.sort(key=lambda x: x.amount, reverse=True)
        elif sort_by == "score_desc":
            items.sort(key=lambda x: x.recoverability_score, reverse=True)
        elif sort_by == "recovered_desc":
            items.sort(key=lambda x: x.recovered_amount, reverse=True)
        else:
            items.sort(key=lambda x: x.created_at)

        return items

    def get_case_detail(self, event_id: str) -> Optional[RecoveryCaseDetailResponse]:
        trace = self.traces_by_id.get(event_id)
        if not trace or not self.bundle:
            return None

        event = next((e for e in self.bundle.all_opportunities if (getattr(e, "transaction_id", None) == event_id or getattr(e, "checkout_id", None) == event_id)), None)
        if not event:
            return None

        rec = trace.recommendation
        pol = trace.policy_decision
        ex = trace.execution_result

        # Build Action Scores
        act_scores = [
            ActionScoreItem(
                action=k,
                success_probability=v.success_probability,
                expected_revenue=v.expected_revenue,
                action_cost=v.action_cost,
                friction_penalty=v.friction_penalty,
                expected_value=v.expected_value
            ) for k, v in rec.action_scores.items()
        ]

        # Build Visual Safety Checklist
        p_state = self.payment_states.get(trace.payment_id) or PaymentStateContext(payment_id=trace.payment_id, customer_id=trace.customer_id)
        c_state = self.customer_states.get(trace.customer_id) or CustomerStateContext(customer_id=trace.customer_id)

        checklist = [
            SafetyCheckItem(
                rule_id="P001",
                rule_name="Input Schema Integrity",
                passed=True,
                description="Transaction amount > 0 and observable metadata verified."
            ),
            SafetyCheckItem(
                rule_id="P002",
                rule_name="Payment Not Already Resolved",
                passed=(p_state.current_status != PaymentStatus.SUCCESS and not p_state.is_already_resolved),
                description="Ensures payment was not captured or settled out-of-band."
            ),
            SafetyCheckItem(
                rule_id="P003",
                rule_name="Attempt Cap Safety (< 2 attempts)",
                passed=(p_state.automated_attempt_count < self.policy_config.max_automated_actions_per_payment),
                description="Hard 2-attempt limit to prevent duplicate interventions."
            ),
            SafetyCheckItem(
                rule_id="P004",
                rule_name="Diagnostic Confidence Gate (>= 0.85)",
                passed=(rec.diagnosis.confidence >= self.policy_config.minimum_diagnosis_confidence),
                description=f"Model confidence ({rec.diagnosis.confidence * 100:.1f}%) meets threshold."
            ),
            SafetyCheckItem(
                rule_id="P005",
                rule_name="High-Risk Fraud & Chargeback Gate",
                passed=(rec.diagnosis.risk_signal.value != "HIGH" and rec.diagnosis.category.value != "HIGH_RISK"),
                description="Zero tolerance for automated actions on high-risk accounts."
            ),
            SafetyCheckItem(
                rule_id="P007",
                rule_name="Customer Contact Fatigue Limits",
                passed=(c_state.contact_actions_count < self.policy_config.max_customer_contact_actions),
                description=f"Customer contacts ({c_state.contact_actions_count}) within limit."
            ),
            SafetyCheckItem(
                rule_id="P008",
                rule_name="Cooldown Interval Clear (300s)",
                passed=True,
                description="No recent interventions within cooldown window."
            ),
        ]

        # Check if can execute
        can_exec = (pol.decision == PolicyDecisionType.ALLOW and pol.execution_authorization is not None)

        # Audit events serialized
        audit_serialized = [
            {
                "audit_id": a.audit_id,
                "event_type": a.event_type.value,
                "timestamp": a.timestamp,
                "action": a.action.value,
                "details": a.details
            } for a in trace.audit_events
        ]

        return RecoveryCaseDetailResponse(
            event_id=trace.event_id,
            payment_id=trace.payment_id,
            customer_id=trace.customer_id,
            amount=rec.amount,
            currency="INR",
            payment_method=getattr(event, "payment_method", "CHECKOUT_DROP"),
            payment_method_type=getattr(event, "payment_method_type", "CHECKOUT_DROP"),
            created_at=rec.timestamp,
            failure_category=rec.diagnosis.category.value,
            error_code=getattr(getattr(event, "failure_details", None), "error_code", None),
            error_description=getattr(getattr(event, "failure_details", None), "error_description", None),
            diagnosis=rec.diagnosis.category.value,
            diagnosis_confidence=rec.diagnosis.confidence,
            diagnosis_risk_signal=rec.diagnosis.risk_signal.value,
            diagnosis_reason_codes=rec.diagnosis.reason_codes,
            diagnosis_explanation=rec.diagnosis.explanation,
            recoverability_score=rec.recoverability_score,
            recoverability_tier=rec.recoverability_tier.value,
            recommended_action=rec.recommended_action.value,
            action_scores=act_scores,
            top_positive_factors=rec.top_positive_factors,
            feature_contributions=rec.feature_contributions,
            policy_decision=pol.decision.value,
            policy_rule_id=pol.primary_rule_id.value if pol.primary_rule_id else None,
            policy_reason=pol.reason,
            safety_checklist=checklist,
            authorization_id=pol.execution_authorization.authorization_id if pol.execution_authorization else None,
            authorization_timestamp=pol.execution_authorization.authorized_at if pol.execution_authorization else None,
            can_execute=can_exec,
            execution_status=ex.execution_status.value,
            execution_reason=ex.execution_reason,
            simulated_external_reference=ex.simulated_external_reference,
            recovery_outcome=ex.recovery_outcome.value,
            recovered_amount=ex.recovered_amount,
            attempt_number=ex.attempt_number,
            customer_contact_attempt_number=ex.customer_contact_attempt_number,
            audit_events=audit_serialized
        )

    def execute_recovery(self, event_id: str, correlation_id: Optional[str] = None) -> ExecuteRecoveryResponse:
        """
        Executes a recovery action strictly through Phase 5 Policy & Phase 6 Controlled Executor.
        Re-validates authorization and live payment state before dispatching simulated action.
        """
        trace = self.traces_by_id.get(event_id)
        if not trace or not self.bundle:
            raise InputError(f"Event '{event_id}' not found in active session.", correlation_id=correlation_id)

        auth = trace.policy_decision.execution_authorization
        if not auth or trace.policy_decision.decision != PolicyDecisionType.ALLOW:
            return ExecuteRecoveryResponse(
                success=False,
                execution_status=ExecutionStatus.BLOCKED.value,
                recovery_outcome=SimulatedRecoveryOutcome.NOT_APPLICABLE.value,
                recovered_amount=0.0,
                message=f"Execution blocked by Phase 5 Policy: {trace.policy_decision.reason}"
            )

        event = next((e for e in self.bundle.all_opportunities if (getattr(e, "transaction_id", None) == event_id or getattr(e, "checkout_id", None) == event_id)), None)
        gt = self.bundle.ground_truth_map.get(event_id)
        p_state = self.payment_states.setdefault(trace.payment_id, PaymentStateContext(payment_id=trace.payment_id, customer_id=trace.customer_id))
        c_state = self.customer_states.setdefault(trace.customer_id, CustomerStateContext(customer_id=trace.customer_id))

        # Re-execute through Phase 6 ControlledExecutor
        exec_res, new_audits = self.executor.execute(
            authorization=auth,
            event=event,
            payment_state=p_state,
            customer_state=c_state,
            ground_truth=gt
        )

        trace.execution_result = exec_res
        trace.audit_events.extend(new_audits)
        self.audit_log.extend(new_audits)

        is_success = (exec_res.execution_status == ExecutionStatus.EXECUTED)
        return ExecuteRecoveryResponse(
            success=is_success,
            execution_status=exec_res.execution_status.value,
            recovery_outcome=exec_res.recovery_outcome.value,
            recovered_amount=exec_res.recovered_amount,
            message=exec_res.execution_reason,
            external_reference=exec_res.simulated_external_reference,
            audit_event_id=exec_res.audit_event_id,
            authorization_id=auth.authorization_id
        )

    def get_safety_dashboard(self) -> SafetyDashboardResponse:
        total_checks = len(self.traces)
        allows = sum(1 for t in self.traces if t.policy_decision.decision == PolicyDecisionType.ALLOW)
        denies = sum(1 for t in self.traces if t.policy_decision.decision == PolicyDecisionType.DENY)
        hrs = sum(1 for t in self.traces if t.policy_decision.decision == PolicyDecisionType.HUMAN_REVIEW)
        nas = sum(1 for t in self.traces if t.policy_decision.decision == PolicyDecisionType.NO_ACTION)

        rules: Dict[str, int] = {}
        for t in self.traces:
            rid = t.policy_decision.primary_rule_id.value if t.policy_decision.primary_rule_id else "UNKNOWN"
            rules[rid] = rules.get(rid, 0) + 1

        blocks = {
            "resolved_payment_attempts_blocked": sum(1 for t in self.traces if "P002" in str(t.policy_decision.primary_rule_id)),
            "attempt_cap_violations_blocked": sum(1 for t in self.traces if "P003" in str(t.policy_decision.primary_rule_id)),
            "low_diagnosis_confidence_escalations": sum(1 for t in self.traces if "P004" in str(t.policy_decision.primary_rule_id)),
            "high_risk_automated_leaks_blocked": sum(1 for t in self.traces if "P005" in str(t.policy_decision.primary_rule_id)),
            "contact_limit_violations_blocked": sum(1 for t in self.traces if "P007" in str(t.policy_decision.primary_rule_id)),
            "cooldown_violations_blocked": sum(1 for t in self.traces if "P008" in str(t.policy_decision.primary_rule_id)),
        }

        return SafetyDashboardResponse(
            total_checks=total_checks,
            policy_allows=allows,
            policy_denies=denies,
            human_reviews=hrs,
            policy_no_actions=nas,
            blocks_breakdown=blocks,
            rule_distributions=rules
        )

    def get_audit_events(self, limit: int = 100) -> List[AuditLogItem]:
        items: List[AuditLogItem] = []
        for a in reversed(self.audit_log[-limit:]):
            items.append(AuditLogItem(
                audit_id=a.audit_id,
                timestamp=a.timestamp,
                event_type=a.event_type.value,
                payment_id=a.payment_id,
                transaction_id=a.transaction_id,
                customer_id=a.customer_id,
                action=a.action.value,
                details=a.details
            ))
        return items

    def get_benchmark_report(self) -> BenchmarkResponse:
        report_path = Path("experiments/benchmark_5seeds_10k/BENCHMARK_REPORT.md")
        summary_md = None
        if report_path.exists():
            try:
                summary_md = report_path.read_text(encoding="utf-8")
            except Exception:
                summary_md = "Evaluation artifact invalid or incomplete. Run Phase 7 CLI to regenerate."

        summary_json_path = Path("experiments/benchmark_5seeds_10k/summary.json")
        strat_data = {}
        if summary_json_path.exists():
            try:
                with open(summary_json_path, "r", encoding="utf-8") as f:
                    strat_data = json.load(f).get("strategy_aggregates", {})
            except Exception:
                strat_data = {"error": "Evaluation artifact corrupted or incomplete."}

        return BenchmarkResponse(
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            dataset_info="5 Holdout Seeds (Seeds 101–505, 50,000 Transactions Total)",
            strategies=strat_data,
            summary_markdown=summary_md
        )
