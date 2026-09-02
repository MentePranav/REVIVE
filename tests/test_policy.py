"""
Comprehensive automated unit, integration, adversarial, and property-style test suite for REVIVE Policy, Safety & Governance Engine.
Covers all Phase 5 requirements, stopping rules, confidence/risk gates, and authorization boundaries.
"""

from datetime import datetime, timezone
import pytest

from agent.models import (
    ActionScore,
    DiagnosisResult,
    NormalizedFailureCategory,
    RecoverabilityTier,
    ReviveRecommendation,
    RiskSignal,
)
from policy.config import ApprovedTemplateRegistry, PolicyConfig
from policy.engine import PolicyEngine
from policy.models import (
    PolicyDecisionType,
    PolicyRuleId,
)
from policy.state_context import CustomerStateContext, PaymentStateContext
from simulator.enums import PaymentStatus, RecoveryAction


@pytest.fixture
def policy_engine():
    return PolicyEngine(PolicyConfig())


@pytest.fixture
def mock_recommendation():
    return ReviveRecommendation(
        event_id="txn_test_p01",
        payment_id="pay_test_p01",
        customer_id="cust_000101",
        timestamp="2026-01-15T12:00:00Z",
        amount=1499.0,
        diagnosis=DiagnosisResult(
            category=NormalizedFailureCategory.TRANSIENT,
            confidence=0.94,
            risk_signal=RiskSignal.LOW,
            reason_codes=["GATEWAY_TIMEOUT"],
            explanation="Transient timeout"
        ),
        recoverability_score=0.92,
        recoverability_tier=RecoverabilityTier.HIGH,
        recommended_action=RecoveryAction.RETRY,
        action_scores={
            RecoveryAction.RETRY.value: ActionScore(
                action=RecoveryAction.RETRY,
                success_probability=0.95,
                expected_revenue=1424.0,
                action_cost=2.0,
                friction_penalty=0.5,
                expected_value=1421.5,
                is_eligible=True
            )
        },
        feature_contributions={"base_category_prior": 0.85},
        top_positive_factors=["Transient timeout"],
        top_negative_factors=[]
    )


# ------------------------------------------------------------------------------
# 20 Required Unit Tests (Section 29)
# ------------------------------------------------------------------------------

def test_1_valid_high_confidence_retry_allowed(policy_engine, mock_recommendation):
    """Test 1: Valid high-confidence retry on unresolved payment -> ALLOW with Authorization Token."""
    p_state = PaymentStateContext(payment_id=mock_recommendation.payment_id, customer_id=mock_recommendation.customer_id)
    decision = policy_engine.evaluate(mock_recommendation, p_state)

    assert decision.decision == PolicyDecisionType.ALLOW
    assert decision.action == RecoveryAction.RETRY
    assert decision.execution_authorization is not None
    assert decision.execution_authorization.authorized is True
    assert decision.execution_authorization.payment_id == mock_recommendation.payment_id


def test_2_low_diagnosis_confidence_triggers_human_review(policy_engine, mock_recommendation):
    """Test 2: Diagnosis confidence < 0.85 -> HUMAN_REVIEW."""
    mock_recommendation.diagnosis.confidence = 0.78
    p_state = PaymentStateContext(payment_id=mock_recommendation.payment_id, customer_id=mock_recommendation.customer_id)
    decision = policy_engine.evaluate(mock_recommendation, p_state)

    assert decision.decision == PolicyDecisionType.HUMAN_REVIEW
    assert decision.primary_rule_id == PolicyRuleId.P004_LOW_DIAGNOSIS_CONFIDENCE
    assert decision.requires_human_review is True
    assert decision.execution_authorization is None


def test_3_high_risk_signal_triggers_human_review(policy_engine, mock_recommendation):
    """Test 3: High-risk signal -> HUMAN_REVIEW."""
    mock_recommendation.diagnosis.risk_signal = RiskSignal.HIGH
    p_state = PaymentStateContext(payment_id=mock_recommendation.payment_id, customer_id=mock_recommendation.customer_id)
    decision = policy_engine.evaluate(mock_recommendation, p_state)

    assert decision.decision == PolicyDecisionType.HUMAN_REVIEW
    assert decision.primary_rule_id == PolicyRuleId.P005_HIGH_RISK_GATE
    assert decision.execution_authorization is None


def test_4_already_captured_payment_denied(policy_engine, mock_recommendation):
    """Test 4: Already captured/resolved payment -> DENY (P002)."""
    p_state = PaymentStateContext(
        payment_id=mock_recommendation.payment_id,
        customer_id=mock_recommendation.customer_id,
        current_status=PaymentStatus.SUCCESS,
        is_already_resolved=True
    )
    decision = policy_engine.evaluate(mock_recommendation, p_state)

    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id == PolicyRuleId.P002_PAYMENT_ALREADY_RESOLVED
    assert decision.execution_authorization is None


def test_5_two_previous_automated_attempts_denied(policy_engine, mock_recommendation):
    """Test 5: Payment with 2 previous automated attempts -> DENY (P003)."""
    p_state = PaymentStateContext(
        payment_id=mock_recommendation.payment_id,
        customer_id=mock_recommendation.customer_id,
        automated_attempt_count=2
    )
    decision = policy_engine.evaluate(mock_recommendation, p_state)

    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id == PolicyRuleId.P003_MAX_AUTOMATED_ATTEMPTS
    assert decision.execution_authorization is None


def test_6_unknown_action_denied(policy_engine, mock_recommendation):
    """Test 6: Unknown action not in allowlist -> DENY (P006)."""
    # Create custom config excluding RETRY
    cfg = PolicyConfig(allowed_actions=[RecoveryAction.DO_NOTHING.value, RecoveryAction.HUMAN_REVIEW.value])
    engine = PolicyEngine(cfg)

    decision = engine.evaluate(mock_recommendation)
    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id == PolicyRuleId.P006_ACTION_NOT_ALLOWLISTED


def test_7_missing_required_fields_denied(policy_engine, mock_recommendation):
    """Test 7: Missing or invalid required fields (e.g. amount <= 0) -> DENY (P001)."""
    mock_recommendation.amount = 0.0
    decision = policy_engine.evaluate(mock_recommendation)

    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id == PolicyRuleId.P001_INVALID_INPUT


def test_8_customer_contact_limit_reached_denied(policy_engine, mock_recommendation):
    """Test 8: Customer reached max contact limit (2) -> Reminder/PaymentLink DENIED (P007)."""
    mock_recommendation.recommended_action = RecoveryAction.REMINDER
    c_state = CustomerStateContext(customer_id=mock_recommendation.customer_id, contact_actions_count=2)

    decision = policy_engine.evaluate(mock_recommendation, customer_state=c_state)
    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id == PolicyRuleId.P007_CUSTOMER_CONTACT_LIMIT


def test_9_cooldown_active_denied(policy_engine, mock_recommendation):
    """Test 9: Action attempted within 5-minute cooldown period -> DENY (P008)."""
    p_state = PaymentStateContext(
        payment_id=mock_recommendation.payment_id,
        customer_id=mock_recommendation.customer_id,
        last_action_timestamp="2026-01-15T11:58:00Z", # 2 mins prior to 12:00:00Z
        automated_attempt_count=1
    )
    decision = policy_engine.evaluate(mock_recommendation, p_state)

    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id == PolicyRuleId.P008_COOLDOWN_ACTIVE


def test_10_valid_reminder_allowed_with_approved_template(policy_engine, mock_recommendation):
    """Test 10: Valid reminder recommendation -> ALLOW with approved template."""
    mock_recommendation.recommended_action = RecoveryAction.REMINDER
    decision = policy_engine.evaluate(mock_recommendation)

    assert decision.decision == PolicyDecisionType.ALLOW
    assert decision.execution_authorization is not None
    assert decision.execution_authorization.template_id == ApprovedTemplateRegistry.REMINDER_STANDARD_V1


def test_11_valid_payment_link_allowed_with_approved_template(policy_engine, mock_recommendation):
    """Test 11: Valid payment link recommendation -> ALLOW with approved template."""
    mock_recommendation.recommended_action = RecoveryAction.PAYMENT_LINK
    decision = policy_engine.evaluate(mock_recommendation)

    assert decision.decision == PolicyDecisionType.ALLOW
    assert decision.execution_authorization is not None
    assert decision.execution_authorization.template_id == ApprovedTemplateRegistry.PAYMENT_LINK_STANDARD_V1


def test_12_arbitrary_action_rejected(policy_engine, mock_recommendation):
    """Test 12: Arbitrary action rejected by allowlist."""
    cfg = PolicyConfig(allowed_actions=[RecoveryAction.DO_NOTHING.value])
    engine = PolicyEngine(cfg)
    decision = engine.evaluate(mock_recommendation)

    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id == PolicyRuleId.P006_ACTION_NOT_ALLOWLISTED


def test_13_arbitrary_communication_template_denied(policy_engine, mock_recommendation):
    """Test 13: Unapproved custom message template -> DENY (P009)."""
    mock_recommendation.recommended_action = RecoveryAction.REMINDER
    decision = policy_engine.evaluate(mock_recommendation, custom_template_id="CUSTOM_PROMO_V99")

    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id == PolicyRuleId.P009_UNAPPROVED_TEMPLATE


def test_14_same_input_produces_identical_decision(policy_engine, mock_recommendation):
    """Test 14: Idempotent and deterministic evaluation."""
    d1 = policy_engine.evaluate(mock_recommendation)
    d2 = policy_engine.evaluate(mock_recommendation)

    assert d1.decision == d2.decision
    assert d1.primary_rule_id == d2.primary_rule_id
    assert d1.reason == d2.reason
    assert d1.policy_version == d2.policy_version


def test_15_policy_version_appears_in_audit_log(policy_engine, mock_recommendation):
    """Test 15: Policy version recorded in audit record."""
    decision = policy_engine.evaluate(mock_recommendation)
    audit = policy_engine.create_audit_record(decision, mock_recommendation)

    assert audit.policy_version == "1.0.0"
    assert audit.final_decision == PolicyDecisionType.ALLOW
    assert audit.is_authorized is True


def test_16_denied_action_produces_no_execution_authorization(policy_engine, mock_recommendation):
    """Test 16: When decision is DENY, execution_authorization is strictly None."""
    p_state = PaymentStateContext(payment_id=mock_recommendation.payment_id, customer_id=mock_recommendation.customer_id, automated_attempt_count=2)
    decision = policy_engine.evaluate(mock_recommendation, p_state)

    assert decision.decision == PolicyDecisionType.DENY
    assert decision.execution_authorization is None


def test_17_allowed_action_produces_valid_execution_authorization(policy_engine, mock_recommendation):
    """Test 17: When decision is ALLOW, execution_authorization is created and valid."""
    decision = policy_engine.evaluate(mock_recommendation)

    assert decision.decision == PolicyDecisionType.ALLOW
    assert decision.execution_authorization is not None
    assert decision.execution_authorization.authorized is True
    assert decision.execution_authorization.action == RecoveryAction.RETRY
    assert decision.execution_authorization.authorization_id.startswith("auth_")


def test_18_resolved_payment_can_never_receive_authorization(policy_engine, mock_recommendation):
    """Test 18: Resolved payment can NEVER receive ExecutionAuthorization under any circumstances."""
    p_state = PaymentStateContext(
        payment_id=mock_recommendation.payment_id,
        customer_id=mock_recommendation.customer_id,
        current_status=PaymentStatus.SUCCESS
    )
    decision = policy_engine.evaluate(mock_recommendation, p_state)

    assert decision.execution_authorization is None
    assert decision.decision == PolicyDecisionType.DENY


def test_19_maximum_attempt_rule_cannot_be_bypassed(policy_engine, mock_recommendation):
    """Test 19: Attempt cap strictly enforced even with 100% confidence and high recoverability."""
    mock_recommendation.recoverability_score = 0.99
    mock_recommendation.diagnosis.confidence = 1.0
    p_state = PaymentStateContext(
        payment_id=mock_recommendation.payment_id,
        customer_id=mock_recommendation.customer_id,
        automated_attempt_count=2
    )
    decision = policy_engine.evaluate(mock_recommendation, p_state)

    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id == PolicyRuleId.P003_MAX_AUTOMATED_ATTEMPTS


def test_20_policy_cannot_be_overridden_by_recoverability_score(policy_engine, mock_recommendation):
    """Test 20: High recoverability score cannot bypass low confidence gate."""
    mock_recommendation.recoverability_score = 0.99
    mock_recommendation.diagnosis.confidence = 0.60 # Low confidence

    decision = policy_engine.evaluate(mock_recommendation)
    assert decision.decision == PolicyDecisionType.HUMAN_REVIEW
    assert decision.primary_rule_id == PolicyRuleId.P004_LOW_DIAGNOSIS_CONFIDENCE


# ------------------------------------------------------------------------------
# Adversarial Attack Scenarios (Section 30)
# ------------------------------------------------------------------------------

def test_attack_a_high_revenue_resolved_payment(policy_engine, mock_recommendation):
    """Attack A: Huge amount + 0.99 recoverability on captured payment -> DENY."""
    mock_recommendation.amount = 1_000_000.0
    mock_recommendation.recoverability_score = 0.99
    p_state = PaymentStateContext(
        payment_id=mock_recommendation.payment_id,
        customer_id=mock_recommendation.customer_id,
        current_status=PaymentStatus.SUCCESS,
        is_already_resolved=True
    )
    decision = policy_engine.evaluate(mock_recommendation, p_state)

    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id == PolicyRuleId.P002_PAYMENT_ALREADY_RESOLVED
    assert decision.execution_authorization is None


def test_attack_b_model_tries_unallowlisted_action(policy_engine, mock_recommendation):
    """Attack B: Action not in approved list -> DENY."""
    cfg = PolicyConfig(allowed_actions=[RecoveryAction.DO_NOTHING.value, RecoveryAction.HUMAN_REVIEW.value])
    engine = PolicyEngine(cfg)

    decision = engine.evaluate(mock_recommendation)
    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id == PolicyRuleId.P006_ACTION_NOT_ALLOWLISTED


def test_attack_c_low_confidence_huge_amount(policy_engine, mock_recommendation):
    """Attack C: Huge amount (500k) with low diagnosis confidence (0.40) -> HUMAN_REVIEW."""
    mock_recommendation.amount = 500_000.0
    mock_recommendation.diagnosis.confidence = 0.40

    decision = policy_engine.evaluate(mock_recommendation)
    assert decision.decision == PolicyDecisionType.HUMAN_REVIEW
    assert decision.requires_human_review is True
    assert decision.execution_authorization is None


def test_attack_d_third_retry_attempt(policy_engine, mock_recommendation):
    """Attack D: 3rd retry attempt -> DENY."""
    p_state = PaymentStateContext(
        payment_id=mock_recommendation.payment_id,
        customer_id=mock_recommendation.customer_id,
        retry_attempt_count=2,
        automated_attempt_count=2
    )
    decision = policy_engine.evaluate(mock_recommendation, p_state)

    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id == PolicyRuleId.P003_MAX_AUTOMATED_ATTEMPTS


def test_attack_e_spam_attempt_contact_limit(policy_engine, mock_recommendation):
    """Attack E: Customer has already received 2 contact actions -> DENY."""
    mock_recommendation.recommended_action = RecoveryAction.PAYMENT_LINK
    c_state = CustomerStateContext(customer_id=mock_recommendation.customer_id, contact_actions_count=2)

    decision = policy_engine.evaluate(mock_recommendation, customer_state=c_state)
    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id == PolicyRuleId.P007_CUSTOMER_CONTACT_LIMIT


def test_attack_f_arbitrary_message_injection(policy_engine, mock_recommendation):
    """Attack F: Arbitrary custom message template injection -> DENY."""
    mock_recommendation.recommended_action = RecoveryAction.REMINDER
    decision = policy_engine.evaluate(mock_recommendation, custom_template_id="EXPLOIT_PAY_NOW_OR_SUSPEND")

    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id == PolicyRuleId.P009_UNAPPROVED_TEMPLATE


# ------------------------------------------------------------------------------
# Property-Style Safety Invariants (Section 31)
# ------------------------------------------------------------------------------

def test_property_safety_invariant_authorization_isolation(policy_engine, mock_recommendation):
    """Property Invariant: Under all failure/block conditions, execution_authorization is strictly None."""
    conditions = [
        # (p_state, c_state, conf, risk, custom_tpl)
        (PaymentStateContext(payment_id="p1", customer_id="c1", current_status=PaymentStatus.SUCCESS), None, 0.95, RiskSignal.LOW, None),
        (PaymentStateContext(payment_id="p1", customer_id="c1", automated_attempt_count=2), None, 0.95, RiskSignal.LOW, None),
        (None, None, 0.50, RiskSignal.LOW, None),
        (None, None, 0.95, RiskSignal.HIGH, None),
        (None, CustomerStateContext(customer_id="c1", contact_actions_count=3), 0.95, RiskSignal.LOW, None),
        (None, None, 0.95, RiskSignal.LOW, "INVALID_TPL"),
    ]

    for p_st, c_st, conf, risk, tpl in conditions:
        rec = mock_recommendation.model_copy(deep=True)
        rec.diagnosis.confidence = conf
        rec.diagnosis.risk_signal = risk
        if tpl or (c_st and c_st.contact_actions_count > 0):
            rec.recommended_action = RecoveryAction.REMINDER

        d = policy_engine.evaluate(rec, payment_state=p_st, customer_state=c_st, custom_template_id=tpl)
        if d.decision != PolicyDecisionType.ALLOW:
            assert d.execution_authorization is None, f"Failed safety invariant: authorization token created for {d.decision} (rule {d.primary_rule_id})"
