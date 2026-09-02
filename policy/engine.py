"""
Zero-Trust Policy, Safety & Governance Engine for REVIVE.
Evaluates contextual recommendations against deterministic safety gates, state rules, and attempt caps.
"""

from datetime import datetime
import uuid
from typing import List, Optional, Tuple

from agent.models import ReviveRecommendation, RiskSignal
from policy.config import ApprovedTemplateRegistry, PolicyConfig
from policy.models import (
    ExecutionAuthorization,
    PolicyAuditRecord,
    PolicyDecision,
    PolicyDecisionType,
    PolicyRuleId,
    PolicyTraceItem,
)
from policy.state_context import CustomerStateContext, PaymentStateContext
from simulator.enums import PaymentStatus, RecoveryAction


class PolicyEngine:
    """The authoritative gatekeeper determining whether a recovery recommendation is authorized."""

    def __init__(self, config: Optional[PolicyConfig] = None):
        self.config = config or PolicyConfig()

    def evaluate(
        self,
        recommendation: ReviveRecommendation,
        payment_state: Optional[PaymentStateContext] = None,
        customer_state: Optional[CustomerStateContext] = None,
        custom_template_id: Optional[str] = None
    ) -> PolicyDecision:
        trace: List[PolicyTraceItem] = []
        rule_ids: List[PolicyRuleId] = []
        action = recommendation.recommended_action
        event_id = recommendation.event_id
        payment_id = recommendation.payment_id or f"pay_{event_id.replace('txn_', '').replace('chk_', '')}"
        customer_id = recommendation.customer_id
        timestamp = recommendation.timestamp

        # Provide default empty states if None
        p_state = payment_state or PaymentStateContext(payment_id=payment_id, customer_id=customer_id)
        c_state = customer_state or CustomerStateContext(customer_id=customer_id)

        # ----------------------------------------------------------------------
        # 1. Input Validity Check (P001)
        # ----------------------------------------------------------------------
        if not event_id or not customer_id or recommendation.amount <= 0.0:
            trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P001_INVALID_INPUT, passed=False, description="Malformed or invalid event metadata."))
            return self._build_decision(
                decision=PolicyDecisionType.DENY,
                action=RecoveryAction.DO_NOTHING,
                event_id=event_id,
                payment_id=payment_id,
                customer_id=customer_id,
                primary_rule=PolicyRuleId.P001_INVALID_INPUT,
                rule_ids=[PolicyRuleId.P001_INVALID_INPUT],
                reason="Input data failed basic schema validity checks.",
                trace=trace,
                timestamp=timestamp
            )
        trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P001_INVALID_INPUT, passed=True, description="Input parameters valid."))

        # ----------------------------------------------------------------------
        # 2. Payment State Check (P002) - Never act on resolved/captured payments
        # ----------------------------------------------------------------------
        if p_state.current_status == PaymentStatus.SUCCESS or p_state.is_already_resolved:
            trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P002_PAYMENT_ALREADY_RESOLVED, passed=False, description="Payment is already resolved/captured."))
            return self._build_decision(
                decision=PolicyDecisionType.DENY,
                action=RecoveryAction.DO_NOTHING,
                event_id=event_id,
                payment_id=payment_id,
                customer_id=customer_id,
                primary_rule=PolicyRuleId.P002_PAYMENT_ALREADY_RESOLVED,
                rule_ids=[PolicyRuleId.P002_PAYMENT_ALREADY_RESOLVED],
                reason="Payment is already resolved; duplicate recovery blocked.",
                trace=trace,
                timestamp=timestamp
            )
        trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P002_PAYMENT_ALREADY_RESOLVED, passed=True, description="Payment is unresolved."))

        # ----------------------------------------------------------------------
        # 3. Hard Safety Stopping Rule (P003) - Max automated attempts cap
        # ----------------------------------------------------------------------
        if action != RecoveryAction.DO_NOTHING:
            if p_state.automated_attempt_count >= self.config.max_automated_actions_per_payment:
                trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P003_MAX_AUTOMATED_ATTEMPTS, passed=False, description=f"Payment has reached max automated attempts cap ({p_state.automated_attempt_count}/{self.config.max_automated_actions_per_payment})."))
                return self._build_decision(
                    decision=PolicyDecisionType.DENY,
                    action=RecoveryAction.DO_NOTHING,
                    event_id=event_id,
                    payment_id=payment_id,
                    customer_id=customer_id,
                    primary_rule=PolicyRuleId.P003_MAX_AUTOMATED_ATTEMPTS,
                    rule_ids=[PolicyRuleId.P003_MAX_AUTOMATED_ATTEMPTS],
                    reason=f"Hard limit of {self.config.max_automated_actions_per_payment} automated attempts reached for this payment.",
                    trace=trace,
                    timestamp=timestamp
                )

            if action == RecoveryAction.RETRY and p_state.retry_attempt_count >= self.config.max_retry_attempts:
                trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P003_MAX_AUTOMATED_ATTEMPTS, passed=False, description=f"Payment has reached max retry attempts cap ({p_state.retry_attempt_count}/{self.config.max_retry_attempts})."))
                return self._build_decision(
                    decision=PolicyDecisionType.DENY,
                    action=RecoveryAction.DO_NOTHING,
                    event_id=event_id,
                    payment_id=payment_id,
                    customer_id=customer_id,
                    primary_rule=PolicyRuleId.P003_MAX_AUTOMATED_ATTEMPTS,
                    rule_ids=[PolicyRuleId.P003_MAX_AUTOMATED_ATTEMPTS],
                    reason=f"Maximum retry attempts ({self.config.max_retry_attempts}) reached for this payment.",
                    trace=trace,
                    timestamp=timestamp
                )
        trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P003_MAX_AUTOMATED_ATTEMPTS, passed=True, description="Attempt count within allowed safety caps."))

        # ----------------------------------------------------------------------
        # 4. Action Allowlist Check (P006)
        # ----------------------------------------------------------------------
        action_val = action.value if hasattr(action, "value") else str(action)
        if action_val not in self.config.allowed_actions:
            trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P006_ACTION_NOT_ALLOWLISTED, passed=False, description=f"Action '{action_val}' is not in approved allowlist."))
            return self._build_decision(
                decision=PolicyDecisionType.DENY,
                action=RecoveryAction.DO_NOTHING,
                event_id=event_id,
                payment_id=payment_id,
                customer_id=customer_id,
                primary_rule=PolicyRuleId.P006_ACTION_NOT_ALLOWLISTED,
                rule_ids=[PolicyRuleId.P006_ACTION_NOT_ALLOWLISTED],
                reason=f"Proposed action '{action_val}' is not in the approved action allowlist.",
                trace=trace,
                timestamp=timestamp
            )
        trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P006_ACTION_NOT_ALLOWLISTED, passed=True, description="Action is allowlisted."))

        # ----------------------------------------------------------------------
        # 5. High-Risk Safety Gate (P005)
        # ----------------------------------------------------------------------
        if recommendation.diagnosis.risk_signal == RiskSignal.HIGH:
            trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P005_HIGH_RISK_GATE, passed=False, description="High risk telemetry detected."))
            if self.config.high_risk_requires_human:
                return self._build_decision(
                    decision=PolicyDecisionType.HUMAN_REVIEW,
                    action=RecoveryAction.HUMAN_REVIEW,
                    event_id=event_id,
                    payment_id=payment_id,
                    customer_id=customer_id,
                    primary_rule=PolicyRuleId.P005_HIGH_RISK_GATE,
                    rule_ids=[PolicyRuleId.P005_HIGH_RISK_GATE],
                    reason="High-risk signal detected; automated recovery blocked pending manual security review.",
                    trace=trace,
                    timestamp=timestamp,
                    requires_human_review=True
                )
            else:
                return self._build_decision(
                    decision=PolicyDecisionType.DENY,
                    action=RecoveryAction.DO_NOTHING,
                    event_id=event_id,
                    payment_id=payment_id,
                    customer_id=customer_id,
                    primary_rule=PolicyRuleId.P005_HIGH_RISK_GATE,
                    rule_ids=[PolicyRuleId.P005_HIGH_RISK_GATE],
                    reason="High-risk signal detected; automated recovery blocked.",
                    trace=trace,
                    timestamp=timestamp
                )
        trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P005_HIGH_RISK_GATE, passed=True, description="Risk signal is within acceptable limits."))

        # ----------------------------------------------------------------------
        # 6. Diagnosis Confidence Gate (P004) - Minimum 0.85
        # ----------------------------------------------------------------------
        if action not in (RecoveryAction.DO_NOTHING, RecoveryAction.HUMAN_REVIEW):
            if recommendation.diagnosis.confidence < self.config.minimum_diagnosis_confidence:
                trace.append(PolicyTraceItem(
                    rule_id=PolicyRuleId.P004_LOW_DIAGNOSIS_CONFIDENCE,
                    passed=False,
                    description=f"Diagnosis confidence ({recommendation.diagnosis.confidence:.2f}) is below threshold ({self.config.minimum_diagnosis_confidence:.2f})."
                ))
                return self._build_decision(
                    decision=PolicyDecisionType.HUMAN_REVIEW,
                    action=RecoveryAction.HUMAN_REVIEW,
                    event_id=event_id,
                    payment_id=payment_id,
                    customer_id=customer_id,
                    primary_rule=PolicyRuleId.P004_LOW_DIAGNOSIS_CONFIDENCE,
                    rule_ids=[PolicyRuleId.P004_LOW_DIAGNOSIS_CONFIDENCE],
                    reason=f"Diagnosis confidence ({recommendation.diagnosis.confidence:.2f}) is below minimum automated threshold ({self.config.minimum_diagnosis_confidence:.2f}).",
                    trace=trace,
                    timestamp=timestamp,
                    requires_human_review=True
                )
        trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P004_LOW_DIAGNOSIS_CONFIDENCE, passed=True, description="Diagnosis confidence meets or exceeds threshold."))

        # ----------------------------------------------------------------------
        # 7. Customer Contact Limit Gate (P007)
        # ----------------------------------------------------------------------
        if action in (RecoveryAction.REMINDER, RecoveryAction.PAYMENT_LINK):
            if c_state.contact_actions_count >= self.config.max_customer_contact_actions:
                trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P007_CUSTOMER_CONTACT_LIMIT, passed=False, description=f"Customer reached max contact limit ({c_state.contact_actions_count}/{self.config.max_customer_contact_actions})."))
                return self._build_decision(
                    decision=PolicyDecisionType.DENY,
                    action=RecoveryAction.DO_NOTHING,
                    event_id=event_id,
                    payment_id=payment_id,
                    customer_id=customer_id,
                    primary_rule=PolicyRuleId.P007_CUSTOMER_CONTACT_LIMIT,
                    rule_ids=[PolicyRuleId.P007_CUSTOMER_CONTACT_LIMIT],
                    reason=f"Customer contact limit ({self.config.max_customer_contact_actions}) reached to prevent messaging fatigue.",
                    trace=trace,
                    timestamp=timestamp
                )
        trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P007_CUSTOMER_CONTACT_LIMIT, passed=True, description="Customer contact limit respected."))

        # ----------------------------------------------------------------------
        # 8. Cooldown Duration Gate (P008)
        # ----------------------------------------------------------------------
        if p_state.last_action_timestamp and timestamp:
            try:
                t_last = datetime.fromisoformat(p_state.last_action_timestamp.replace("Z", "+00:00"))
                t_curr = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                diff_sec = (t_curr - t_last).total_seconds()
                if 0 <= diff_sec < self.config.minimum_action_cooldown_seconds:
                    trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P008_COOLDOWN_ACTIVE, passed=False, description=f"Cooldown active: {diff_sec:.0f}s elapsed (min {self.config.minimum_action_cooldown_seconds}s required)."))
                    return self._build_decision(
                        decision=PolicyDecisionType.DENY,
                        action=RecoveryAction.DO_NOTHING,
                        event_id=event_id,
                        payment_id=payment_id,
                        customer_id=customer_id,
                        primary_rule=PolicyRuleId.P008_COOLDOWN_ACTIVE,
                        rule_ids=[PolicyRuleId.P008_COOLDOWN_ACTIVE],
                        reason=f"Intervention blocked because cooldown period ({self.config.minimum_action_cooldown_seconds}s) has not elapsed.",
                        trace=trace,
                        timestamp=timestamp
                    )
            except Exception:
                pass
        trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P008_COOLDOWN_ACTIVE, passed=True, description="Cooldown interval satisfied."))

        # ----------------------------------------------------------------------
        # 9. Approved Template Check (P009)
        # ----------------------------------------------------------------------
        selected_template_id = None
        if action in (RecoveryAction.REMINDER, RecoveryAction.PAYMENT_LINK):
            is_chk = "chk_" in event_id
            assigned_tpl = custom_template_id or ApprovedTemplateRegistry.get_template_for_action(action, is_chk)
            if assigned_tpl not in self.config.approved_templates:
                trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P009_UNAPPROVED_TEMPLATE, passed=False, description=f"Template '{assigned_tpl}' is not in approved template registry."))
                return self._build_decision(
                    decision=PolicyDecisionType.DENY,
                    action=RecoveryAction.DO_NOTHING,
                    event_id=event_id,
                    payment_id=payment_id,
                    customer_id=customer_id,
                    primary_rule=PolicyRuleId.P009_UNAPPROVED_TEMPLATE,
                    rule_ids=[PolicyRuleId.P009_UNAPPROVED_TEMPLATE],
                    reason="Communication action rejected due to unapproved message template.",
                    trace=trace,
                    timestamp=timestamp
                )
            selected_template_id = assigned_tpl
            trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P009_UNAPPROVED_TEMPLATE, passed=True, description=f"Approved template '{assigned_tpl}' selected."))

        # ----------------------------------------------------------------------
        # 10. Final Authorization Decision (P010)
        # ----------------------------------------------------------------------
        if action == RecoveryAction.DO_NOTHING:
            trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P010_ACTION_APPROVED, passed=True, description="No intervention required."))
            return self._build_decision(
                decision=PolicyDecisionType.NO_ACTION,
                action=RecoveryAction.DO_NOTHING,
                event_id=event_id,
                payment_id=payment_id,
                customer_id=customer_id,
                primary_rule=PolicyRuleId.P010_ACTION_APPROVED,
                rule_ids=[PolicyRuleId.P010_ACTION_APPROVED],
                reason="No active intervention required.",
                trace=trace,
                timestamp=timestamp
            )

        if action == RecoveryAction.HUMAN_REVIEW:
            trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P010_ACTION_APPROVED, passed=True, description="Human review requested."))
            return self._build_decision(
                decision=PolicyDecisionType.HUMAN_REVIEW,
                action=RecoveryAction.HUMAN_REVIEW,
                event_id=event_id,
                payment_id=payment_id,
                customer_id=customer_id,
                primary_rule=PolicyRuleId.P010_ACTION_APPROVED,
                rule_ids=[PolicyRuleId.P010_ACTION_APPROVED],
                reason="Escalated to human review queue.",
                trace=trace,
                timestamp=timestamp,
                requires_human_review=True
            )

        # Generate ExecutionAuthorization ONLY for ALLOW
        auth_token = ExecutionAuthorization(
            authorization_id=f"auth_{uuid.uuid4().hex[:12]}",
            authorized=True,
            payment_id=payment_id,
            transaction_id=event_id if "txn_" in event_id else None,
            customer_id=customer_id,
            action=action,
            template_id=selected_template_id,
            policy_version=self.config.policy_version,
            authorized_at=timestamp
        )

        trace.append(PolicyTraceItem(rule_id=PolicyRuleId.P010_ACTION_APPROVED, passed=True, description="All policy gates passed; execution authorized."))
        return self._build_decision(
            decision=PolicyDecisionType.ALLOW,
            action=action,
            event_id=event_id,
            payment_id=payment_id,
            customer_id=customer_id,
            primary_rule=PolicyRuleId.P010_ACTION_APPROVED,
            rule_ids=[t.rule_id for t in trace if t.passed],
            reason=f"Recovery action '{action.value}' approved by policy governance engine.",
            trace=trace,
            timestamp=timestamp,
            execution_authorization=auth_token
        )

    def _build_decision(
        self,
        decision: PolicyDecisionType,
        action: RecoveryAction,
        event_id: str,
        payment_id: str,
        customer_id: str,
        primary_rule: PolicyRuleId,
        rule_ids: List[PolicyRuleId],
        reason: str,
        trace: List[PolicyTraceItem],
        timestamp: str,
        requires_human_review: bool = False,
        execution_authorization: Optional[ExecutionAuthorization] = None
    ) -> PolicyDecision:
        return PolicyDecision(
            decision=decision,
            action=action,
            event_id=event_id,
            payment_id=payment_id,
            customer_id=customer_id,
            primary_rule_id=primary_rule,
            policy_rule_ids=rule_ids,
            reason=reason,
            requires_human_review=requires_human_review,
            policy_version=self.config.policy_version,
            timestamp=timestamp,
            evaluation_trace=trace,
            execution_authorization=execution_authorization
        )

    @classmethod
    def create_audit_record(
        cls,
        decision: PolicyDecision,
        recommendation: ReviveRecommendation,
        attempt_count: int = 0
    ) -> PolicyAuditRecord:
        """Generates a structured, machine-readable audit record for governance monitoring."""
        return PolicyAuditRecord(
            audit_id=f"audit_{uuid.uuid4().hex[:12]}",
            event_id=decision.event_id,
            payment_id=decision.payment_id,
            customer_id=decision.customer_id,
            timestamp=decision.timestamp,
            recommended_action=recommendation.recommended_action.value,
            final_decision=decision.decision,
            primary_rule_id=decision.primary_rule_id,
            policy_rule_ids=[r.value for r in decision.policy_rule_ids],
            diagnosis_confidence=recommendation.diagnosis.confidence,
            recoverability_score=recommendation.recoverability_score,
            risk_signal=recommendation.diagnosis.risk_signal.value,
            attempt_count=attempt_count,
            policy_version=decision.policy_version,
            reason=decision.reason,
            is_authorized=decision.execution_authorization is not None
        )
