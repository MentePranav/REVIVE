"""
Controlled Recovery Execution Simulator for REVIVE.
Enforces zero-trust execution boundaries, idempotency, live state safety checks, and synthetic outcome recording.
"""

from datetime import datetime, timezone
import hashlib
from typing import Dict, List, Optional, Tuple, Union
import uuid

from execution.models import (
    AuditEventType,
    ExecutionAuditEvent,
    ExecutionResult,
    ExecutionStatus,
    SimulatedRecoveryOutcome,
)
from policy.config import ApprovedTemplateRegistry, PolicyConfig
from policy.models import ExecutionAuthorization
from policy.state_context import CustomerStateContext, PaymentStateContext
from simulator.enums import PaymentStatus, RecoveryAction, RecoveryOutcome
from simulator.ground_truth_schema import GroundTruthRecord
from simulator.public_schema import AbandonedCheckout, Transaction


class ControlledExecutor:
    """
    Controlled execution engine.
    Executes recovery actions strictly under valid ExecutionAuthorization tokens.
    """

    def __init__(self, config: Optional[PolicyConfig] = None):
        self.config = config or PolicyConfig()
        self.executor_version = "1.0.0"
        self.execution_cache: Dict[str, ExecutionResult] = {}
        self.audit_log: List[ExecutionAuditEvent] = []

    def execute(
        self,
        authorization: Optional[ExecutionAuthorization],
        event: Union[Transaction, AbandonedCheckout],
        payment_state: Optional[PaymentStateContext] = None,
        customer_state: Optional[CustomerStateContext] = None,
        ground_truth: Optional[GroundTruthRecord] = None,
        executed_at: Optional[str] = None
    ) -> Tuple[ExecutionResult, List[ExecutionAuditEvent]]:
        """
        Executes an authorized recovery action within a controlled simulation boundary.
        """
        local_audit: List[ExecutionAuditEvent] = []
        event_id = event.transaction_id if isinstance(event, Transaction) else event.checkout_id
        payment_id = getattr(event, "payment_id", None) or f"pay_{event_id.replace('txn_', '').replace('chk_', '')}"
        customer_id = event.customer_id
        timestamp = executed_at or getattr(event, "created_at", datetime.now(timezone.utc).isoformat())

        # ----------------------------------------------------------------------
        # 1. Audit Request Initiation
        # ----------------------------------------------------------------------
        req_audit = ExecutionAuditEvent(
            audit_id=f"aud_{uuid.uuid4().hex[:10]}",
            event_type=AuditEventType.REQUESTED,
            payment_id=payment_id,
            transaction_id=event_id if "txn_" in event_id else None,
            customer_id=customer_id,
            action=authorization.action if authorization else RecoveryAction.DO_NOTHING,
            timestamp=timestamp,
            details={"has_authorization": authorization is not None}
        )
        local_audit.append(req_audit)

        # ----------------------------------------------------------------------
        # 2. Strict Authorization Validation
        # ----------------------------------------------------------------------
        if not authorization:
            return self._fail_closed(
                reason="EXECUTION_BLOCKED_MISSING_AUTHORIZATION: No ExecutionAuthorization token provided.",
                status=ExecutionStatus.BLOCKED,
                event_id=event_id,
                payment_id=payment_id,
                customer_id=customer_id,
                action=RecoveryAction.DO_NOTHING,
                timestamp=timestamp,
                local_audit=local_audit
            )

        if not authorization.authorized:
            return self._fail_closed(
                reason="EXECUTION_BLOCKED_UNAUTHORIZED: Token marked as unauthorized.",
                status=ExecutionStatus.BLOCKED,
                event_id=event_id,
                payment_id=payment_id,
                customer_id=customer_id,
                action=authorization.action,
                timestamp=timestamp,
                local_audit=local_audit,
                auth_id=authorization.authorization_id
            )

        # Validate token metadata alignment
        if authorization.customer_id != customer_id:
            return self._fail_closed(
                reason=f"EXECUTION_BLOCKED_CUSTOMER_MISMATCH: Token customer ({authorization.customer_id}) != Event customer ({customer_id}).",
                status=ExecutionStatus.BLOCKED,
                event_id=event_id,
                payment_id=payment_id,
                customer_id=customer_id,
                action=authorization.action,
                timestamp=timestamp,
                local_audit=local_audit,
                auth_id=authorization.authorization_id
            )

        if authorization.payment_id and authorization.payment_id != payment_id:
            return self._fail_closed(
                reason=f"EXECUTION_BLOCKED_PAYMENT_MISMATCH: Token payment ({authorization.payment_id}) != Event payment ({payment_id}).",
                status=ExecutionStatus.BLOCKED,
                event_id=event_id,
                payment_id=payment_id,
                customer_id=customer_id,
                action=authorization.action,
                timestamp=timestamp,
                local_audit=local_audit,
                auth_id=authorization.authorization_id
            )

        if authorization.authorized_at:
            try:
                auth_dt = datetime.fromisoformat(authorization.authorized_at.replace("Z", "+00:00"))
                curr_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if (curr_dt - auth_dt).total_seconds() > 86400: # Stale by >24h
                    return self._fail_closed(
                        reason="EXECUTION_BLOCKED_STALE_AUTHORIZATION: Authorization token timestamp is expired/stale.",
                        status=ExecutionStatus.BLOCKED,
                        event_id=event_id,
                        payment_id=payment_id,
                        customer_id=customer_id,
                        action=authorization.action,
                        timestamp=timestamp,
                        local_audit=local_audit,
                        auth_id=authorization.authorization_id
                    )
            except Exception:
                pass

        if authorization.action.value not in self.config.allowed_actions:
            return self._fail_closed(
                reason=f"EXECUTION_BLOCKED_UNSUPPORTED_ACTION: Action '{authorization.action.value}' not allowed.",
                status=ExecutionStatus.BLOCKED,
                event_id=event_id,
                payment_id=payment_id,
                customer_id=customer_id,
                action=authorization.action,
                timestamp=timestamp,
                local_audit=local_audit,
                auth_id=authorization.authorization_id
            )

        # ----------------------------------------------------------------------
        # 3. Deterministic Idempotency Key & Duplicate Check
        # ----------------------------------------------------------------------
        idempotency_raw = f"{payment_id}:{authorization.authorization_id}:{authorization.action.value}"
        execution_key = hashlib.sha256(idempotency_raw.encode("utf-8")).hexdigest()[:16]

        if execution_key in self.execution_cache:
            dup_result = self.execution_cache[execution_key]
            dup_audit = ExecutionAuditEvent(
                audit_id=f"aud_{uuid.uuid4().hex[:10]}",
                event_type=AuditEventType.DUPLICATE,
                payment_id=payment_id,
                transaction_id=event_id if "txn_" in event_id else None,
                customer_id=customer_id,
                action=authorization.action,
                timestamp=timestamp,
                details={"execution_key": execution_key, "original_execution_id": dup_result.execution_id}
            )
            local_audit.append(dup_audit)
            self.audit_log.extend(local_audit)
            return dup_result, local_audit

        # Audit Authorization Passed
        val_audit = ExecutionAuditEvent(
            audit_id=f"aud_{uuid.uuid4().hex[:10]}",
            event_type=AuditEventType.AUTHORIZATION_VALIDATED,
            payment_id=payment_id,
            transaction_id=event_id if "txn_" in event_id else None,
            customer_id=customer_id,
            action=authorization.action,
            timestamp=timestamp,
            details={"authorization_id": authorization.authorization_id, "policy_version": authorization.policy_version}
        )
        local_audit.append(val_audit)

        # ----------------------------------------------------------------------
        # 4. Live Payment State Re-Validation (Race Condition Guard)
        # ----------------------------------------------------------------------
        p_state = payment_state or PaymentStateContext(payment_id=payment_id, customer_id=customer_id)
        if p_state.current_status == PaymentStatus.SUCCESS or p_state.is_already_resolved:
            return self._fail_closed(
                reason="EXECUTION_BLOCKED_PAYMENT_STATE_CHANGED: Payment status changed to resolved prior to execution.",
                status=ExecutionStatus.BLOCKED,
                event_id=event_id,
                payment_id=payment_id,
                customer_id=customer_id,
                action=authorization.action,
                timestamp=timestamp,
                local_audit=local_audit,
                auth_id=authorization.authorization_id,
                key=execution_key
            )

        # ----------------------------------------------------------------------
        # 5. Live Attempt Count & Fatigue Safety Checks
        # ----------------------------------------------------------------------
        if p_state.automated_attempt_count >= self.config.max_automated_actions_per_payment:
            return self._fail_closed(
                reason=f"EXECUTION_BLOCKED_MAX_ATTEMPTS: Payment reached maximum automated attempts ({p_state.automated_attempt_count}).",
                status=ExecutionStatus.BLOCKED,
                event_id=event_id,
                payment_id=payment_id,
                customer_id=customer_id,
                action=authorization.action,
                timestamp=timestamp,
                local_audit=local_audit,
                auth_id=authorization.authorization_id,
                key=execution_key
            )

        c_state = customer_state or CustomerStateContext(customer_id=customer_id)
        if authorization.action in (RecoveryAction.REMINDER, RecoveryAction.PAYMENT_LINK):
            if c_state.contact_actions_count >= self.config.max_customer_contact_actions:
                return self._fail_closed(
                    reason=f"EXECUTION_BLOCKED_CONTACT_LIMIT: Customer reached {c_state.contact_actions_count} contact attempts.",
                    status=ExecutionStatus.BLOCKED,
                    event_id=event_id,
                    payment_id=payment_id,
                    customer_id=customer_id,
                    action=authorization.action,
                    timestamp=timestamp,
                    local_audit=local_audit,
                    auth_id=authorization.authorization_id,
                    key=execution_key
                )

        # ----------------------------------------------------------------------
        # 6. Simulated Action Dispatch
        # ----------------------------------------------------------------------
        action = authorization.action
        ref_hash = hashlib.sha256(f"{payment_id}:{timestamp}".encode()).hexdigest()[:10]

        if action == RecoveryAction.RETRY:
            ext_ref = f"sim_ret_{ref_hash}"
            exec_status = ExecutionStatus.EXECUTED
            exec_reason = "Simulated payment retry dispatched to synthetic gateway."
        elif action == RecoveryAction.REMINDER:
            ext_ref = f"sim_rem_{ref_hash}"
            exec_status = ExecutionStatus.EXECUTED
            exec_reason = f"Simulated reminder dispatched using template '{authorization.template_id or 'REMINDER_STANDARD_V1'}'."
        elif action == RecoveryAction.PAYMENT_LINK:
            ext_ref = f"sim_pl_{ref_hash}"
            exec_status = ExecutionStatus.EXECUTED
            exec_reason = f"Synthetic payment link generated ({ext_ref}) using template '{authorization.template_id or 'PAYMENT_LINK_STANDARD_V1'}'."
        elif action == RecoveryAction.HUMAN_REVIEW:
            ext_ref = f"sim_rev_{ref_hash}"
            exec_status = ExecutionStatus.HUMAN_REVIEW_REQUIRED
            exec_reason = "Payment routed to human review queue; no automated action taken."
        else: # DO_NOTHING
            ext_ref = None
            exec_status = ExecutionStatus.NO_ACTION_TAKEN
            exec_reason = "No recovery action authorized; observation only."

        # Audit Execution Step
        exec_audit = ExecutionAuditEvent(
            audit_id=f"aud_{uuid.uuid4().hex[:10]}",
            event_type=AuditEventType.EXECUTED,
            payment_id=payment_id,
            transaction_id=event_id if "txn_" in event_id else None,
            customer_id=customer_id,
            action=action,
            timestamp=timestamp,
            details={"execution_status": exec_status.value, "external_reference": ext_ref}
        )
        local_audit.append(exec_audit)

        # ----------------------------------------------------------------------
        # 7. Synthetic Outcome Simulation (Phase 2 Integration)
        # ----------------------------------------------------------------------
        recovery_outcome = SimulatedRecoveryOutcome.NOT_APPLICABLE
        recovered_amount = 0.0

        if exec_status == ExecutionStatus.EXECUTED and ground_truth:
            if ground_truth.is_already_resolved:
                recovery_outcome = SimulatedRecoveryOutcome.NATURAL_RECOVERY
                recovered_amount = event.amount
            else:
                cf_result = ground_truth.counterfactual_outcomes.get(action.value, "FAILURE")
                if cf_result in ("SUCCESS", RecoveryOutcome.SUCCESS.value):
                    recovery_outcome = SimulatedRecoveryOutcome.RECOVERED
                    recovered_amount = event.amount
                elif cf_result in ("ALREADY_RESOLVED", RecoveryOutcome.ALREADY_RESOLVED.value):
                    recovery_outcome = SimulatedRecoveryOutcome.NATURAL_RECOVERY
                    recovered_amount = event.amount
                else:
                    recovery_outcome = SimulatedRecoveryOutcome.NOT_RECOVERED
                    recovered_amount = 0.0

        # Audit Outcome Recorded
        outcome_audit = ExecutionAuditEvent(
            audit_id=f"aud_{uuid.uuid4().hex[:10]}",
            event_type=AuditEventType.OUTCOME_RECORDED,
            payment_id=payment_id,
            transaction_id=event_id if "txn_" in event_id else None,
            customer_id=customer_id,
            action=action,
            timestamp=timestamp,
            details={"recovery_outcome": recovery_outcome.value, "recovered_amount": recovered_amount}
        )
        local_audit.append(outcome_audit)

        # ----------------------------------------------------------------------
        # 8. Assemble & Cache ExecutionResult
        # ----------------------------------------------------------------------
        result = ExecutionResult(
            execution_id=f"exec_{uuid.uuid4().hex[:12]}",
            execution_key=execution_key,
            authorization_id=authorization.authorization_id,
            transaction_id=event_id if "txn_" in event_id else None,
            payment_id=payment_id,
            customer_id=customer_id,
            authorized_action=action,
            execution_status=exec_status,
            execution_reason=exec_reason,
            executed_at=timestamp,
            attempt_number=p_state.automated_attempt_count + 1,
            customer_contact_attempt_number=c_state.contact_actions_count + (1 if action in (RecoveryAction.REMINDER, RecoveryAction.PAYMENT_LINK) else 0),
            simulated_external_reference=ext_ref,
            recovery_outcome=recovery_outcome,
            recovered_amount=recovered_amount,
            audit_event_id=outcome_audit.audit_id,
            policy_version=authorization.policy_version,
            executor_version=self.executor_version
        )

        self.execution_cache[execution_key] = result
        self.audit_log.extend(local_audit)

        return result, local_audit

    def _fail_closed(
        self,
        reason: str,
        status: ExecutionStatus,
        event_id: str,
        payment_id: str,
        customer_id: str,
        action: RecoveryAction,
        timestamp: str,
        local_audit: List[ExecutionAuditEvent],
        auth_id: Optional[str] = None,
        key: Optional[str] = None
    ) -> Tuple[ExecutionResult, List[ExecutionAuditEvent]]:
        """Safely fails closed without triggering unverified retries or operations."""
        block_audit = ExecutionAuditEvent(
            audit_id=f"aud_{uuid.uuid4().hex[:10]}",
            event_type=AuditEventType.BLOCKED,
            payment_id=payment_id,
            transaction_id=event_id if "txn_" in event_id else None,
            customer_id=customer_id,
            action=action,
            timestamp=timestamp,
            details={"reason": reason, "authorization_id": auth_id}
        )
        local_audit.append(block_audit)
        self.audit_log.extend(local_audit)

        exec_key = key or hashlib.sha256(f"{payment_id}:{auth_id or 'none'}:{action.value}".encode()).hexdigest()[:16]

        result = ExecutionResult(
            execution_id=f"exec_{uuid.uuid4().hex[:12]}",
            execution_key=exec_key,
            authorization_id=auth_id,
            transaction_id=event_id if "txn_" in event_id else None,
            payment_id=payment_id,
            customer_id=customer_id,
            authorized_action=action,
            execution_status=status,
            execution_reason=reason,
            executed_at=timestamp,
            attempt_number=0,
            customer_contact_attempt_number=0,
            simulated_external_reference=None,
            recovery_outcome=SimulatedRecoveryOutcome.NOT_APPLICABLE,
            recovered_amount=0.0,
            audit_event_id=block_audit.audit_id,
            policy_version=self.config.policy_version,
            executor_version=self.executor_version
        )
        return result, local_audit
