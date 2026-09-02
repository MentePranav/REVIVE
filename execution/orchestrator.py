"""
End-to-End Recovery Orchestrator for REVIVE.
Coordinates: Raw Failure -> Phase 4 Scoring -> Phase 5 Policy -> Phase 6 Execution -> Audit Trail.
"""

from typing import Optional, Union

from agent.engine import ReviveEngine
from execution.executor import ControlledExecutor
from execution.models import (
    ExecutionLifecycleTrace,
    ExecutionResult,
    ExecutionStatus,
    SimulatedRecoveryOutcome,
)
from policy.config import PolicyConfig
from policy.engine import PolicyEngine
from policy.models import PolicyDecisionType
from policy.state_context import CustomerStateContext, PaymentStateContext
from simulator.enums import RecoveryAction
from simulator.ground_truth_schema import GroundTruthRecord
from simulator.public_schema import AbandonedCheckout, Customer, Transaction


class ReviveOrchestrator:
    """End-to-end coordinator ensuring strict policy governance before simulated execution."""

    def __init__(self, policy_config: Optional[PolicyConfig] = None):
        self.policy_config = policy_config or PolicyConfig()
        self.policy_engine = PolicyEngine(self.policy_config)
        self.executor = ControlledExecutor(self.policy_config)

    def process_event(
        self,
        event: Union[Transaction, AbandonedCheckout],
        customer: Optional[Customer] = None,
        payment_state: Optional[PaymentStateContext] = None,
        customer_state: Optional[CustomerStateContext] = None,
        ground_truth: Optional[GroundTruthRecord] = None
    ) -> ExecutionLifecycleTrace:
        """
        Executes the full REVIVE lifecycle on a single failure or checkout drop-off event.
        Guarantees that no execution occurs without explicit PolicyEngine ALLOW authorization.
        """
        event_id = event.transaction_id if isinstance(event, Transaction) else event.checkout_id
        payment_id = f"pay_{event_id.replace('txn_', '').replace('chk_', '')}"
        customer_id = event.customer_id

        # ----------------------------------------------------------------------
        # 1. Phase 4: Contextual Diagnosis & Recovery Scoring
        # ----------------------------------------------------------------------
        recommendation = ReviveEngine.evaluate(event, customer)

        # ----------------------------------------------------------------------
        # 2. Phase 5: Zero-Trust Policy & Safety Governance
        # ----------------------------------------------------------------------
        p_state = payment_state or PaymentStateContext(payment_id=payment_id, customer_id=customer_id)
        c_state = customer_state or CustomerStateContext(customer_id=customer_id)
        policy_decision = self.policy_engine.evaluate(recommendation, p_state, c_state)

        # ----------------------------------------------------------------------
        # 3. Phase 6: Controlled Execution Boundary
        # ----------------------------------------------------------------------
        if policy_decision.decision == PolicyDecisionType.ALLOW and policy_decision.execution_authorization:
            # Policy explicitly AUTHORIZED execution
            exec_result, audit_events = self.executor.execute(
                authorization=policy_decision.execution_authorization,
                event=event,
                payment_state=p_state,
                customer_state=c_state,
                ground_truth=ground_truth
            )
        else:
            # Policy did NOT authorize automated execution -> Execution is structurally blocked
            if policy_decision.decision == PolicyDecisionType.HUMAN_REVIEW:
                status = ExecutionStatus.HUMAN_REVIEW_REQUIRED
            elif policy_decision.decision == PolicyDecisionType.NO_ACTION:
                status = ExecutionStatus.NO_ACTION_TAKEN
            else:
                status = ExecutionStatus.BLOCKED

            exec_result, audit_events = self.executor._fail_closed(
                reason=f"POLICY_GATE_{policy_decision.decision.value}: {policy_decision.reason}",
                status=status,
                event_id=event_id,
                payment_id=payment_id,
                customer_id=customer_id,
                action=policy_decision.action,
                timestamp=event.created_at,
                local_audit=[]
            )

        return ExecutionLifecycleTrace(
            event_id=event_id,
            payment_id=payment_id,
            customer_id=customer_id,
            recommendation=recommendation,
            policy_decision=policy_decision,
            execution_result=exec_result,
            audit_events=audit_events
        )
