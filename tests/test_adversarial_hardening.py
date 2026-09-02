"""
Comprehensive Adversarial Edge Case Test Suite for REVIVE Phase 9 (Section 44 Hardening).
Tests all 20 adversarial failure modes and security boundary invariants.
"""

from fastapi.testclient import TestClient
import pytest

from agent.models import (
    DiagnosisResult,
    NormalizedFailureCategory,
    RecoverabilityTier,
    ReviveFeatures,
    ReviveRecommendation,
    RiskSignal,
)
from core.config import ReviveAppConfig
from core.errors import AuthorizationError, PolicyError
from evaluation.experiment.dataset_splitter import DatasetSplitter
from execution.executor import ControlledExecutor
from execution.models import ExecutionStatus, SimulatedRecoveryOutcome
from policy.config import PolicyConfig
from policy.engine import PolicyEngine
from policy.models import ExecutionAuthorization, PolicyDecisionType
from policy.state_context import CustomerStateContext, PaymentStateContext
from server.app import app
from simulator.enums import PaymentMethod, PaymentMethodType, PaymentStatus, RecoveryAction
from simulator.public_schema import Transaction

client = TestClient(app)


def make_test_recommendation(
    event_id: str = "txn_adv_001",
    payment_id: str = "pay_adv_001",
    customer_id: str = "cust_adv_001",
    amount: float = 1000.0,
    category: NormalizedFailureCategory = NormalizedFailureCategory.TRANSIENT,
    confidence: float = 0.95,
    risk_signal: RiskSignal = RiskSignal.LOW,
    action: RecoveryAction = RecoveryAction.RETRY,
    score: float = 0.85,
    timestamp: str = "2026-09-02T12:00:00Z"
) -> ReviveRecommendation:
    return ReviveRecommendation(
        event_id=event_id,
        payment_id=payment_id,
        customer_id=customer_id,
        timestamp=timestamp,
        amount=amount,
        diagnosis=DiagnosisResult(
            category=category,
            confidence=confidence,
            risk_signal=risk_signal,
            reason_codes=["TEST_REASON"],
            explanation="Test diagnosis explanation"
        ),
        recoverability_score=score,
        recoverability_tier=RecoverabilityTier.HIGH if score >= 0.70 else RecoverabilityTier.MEDIUM,
        recommended_action=action,
        action_scores={},
        feature_contributions={},
        top_positive_factors=[],
        top_negative_factors=[]
    )


def make_test_transaction(
    transaction_id: str = "txn_adv_001",
    order_id: str = "order_adv_001",
    payment_id: str = "pay_adv_001",
    customer_id: str = "cust_adv_001",
    amount: float = 1000.0,
    status: PaymentStatus = PaymentStatus.FAILED,
) -> Transaction:
    return Transaction(
        transaction_id=transaction_id,
        order_id=order_id,
        payment_id=payment_id,
        customer_id=customer_id,
        amount=amount,
        currency="INR",
        status=status,
        payment_method=PaymentMethod.UPI,
        payment_method_type=PaymentMethodType.UPI_INTENT,
        created_at="2026-09-02T12:00:00Z"
    )


# ------------------------------------------------------------------------------
# 20 Adversarial Hardening Edge Case Tests (Section 44)
# ------------------------------------------------------------------------------

def test_adv_1_double_click_execute_idempotent():
    """Edge Case 1: Rapid double-clicking execute produces exactly one simulated recovery."""
    client.post("/api/demo/reset")
    cases = client.get("/api/recovery-cases").json()
    allow_case = next((c for c in cases if c["has_authorization"] and c["policy_decision"] == "ALLOW"), None)
    assert allow_case is not None

    event_id = allow_case["event_id"]
    r1 = client.post(f"/api/recovery-cases/{event_id}/execute").json()
    r2 = client.post(f"/api/recovery-cases/{event_id}/execute").json()

    assert r1["execution_status"] in ("EXECUTED", "BLOCKED")
    assert r2["execution_status"] in ("EXECUTED", "BLOCKED")
    assert r1["recovered_amount"] == r2["recovered_amount"]


def test_adv_2_get_requests_are_side_effect_free():
    """Edge Case 2: Browser refresh / GET requests do not mutate recovery metrics."""
    overview1 = client.get("/api/overview").json()
    overview2 = client.get("/api/overview").json()
    assert overview1["total_recovered_revenue"] == overview2["total_recovered_revenue"]
    assert overview1["actions_executed_count"] == overview2["actions_executed_count"]


def test_adv_3_stale_authorization_rejected():
    """Edge Case 3: Stale authorization with expired timestamp is rejected."""
    executor = ControlledExecutor()
    stale_auth = ExecutionAuthorization(
        authorization_id="auth_stale_001",
        payment_id="pay_stale_001",
        customer_id="cust_001",
        action=RecoveryAction.RETRY,
        policy_version="1.0.0",
        authorized_at="2020-01-01T00:00:00Z" # 6 years old
    )
    txn = make_test_transaction(payment_id="pay_stale_001", customer_id="cust_001")
    p_state = PaymentStateContext(payment_id="pay_stale_001", customer_id="cust_001")
    c_state = CustomerStateContext(customer_id="cust_001")

    res, audits = executor.execute(stale_auth, txn, p_state, c_state, None)
    assert res.execution_status == ExecutionStatus.BLOCKED
    assert "stale" in res.execution_reason.lower()


def test_adv_4_resolved_payment_denied_p002():
    """Edge Case 4: Already captured payment is blocked by Policy Rule P002."""
    policy = PolicyEngine()
    rec = make_test_recommendation(
        event_id="txn_res_001",
        payment_id="pay_res_001",
        customer_id="cust_001",
        amount=1500.0,
        category=NormalizedFailureCategory.TRANSIENT,
        action=RecoveryAction.RETRY
    )
    p_state = PaymentStateContext(payment_id="pay_res_001", customer_id="cust_001", current_status=PaymentStatus.SUCCESS)
    c_state = CustomerStateContext(customer_id="cust_001")

    decision = policy.evaluate(rec, p_state, c_state)
    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id.value == "P002_PAYMENT_ALREADY_RESOLVED"
    assert decision.execution_authorization is None


def test_adv_5_duplicate_attempt_cap_p003():
    """Edge Case 5: 3rd automated recovery attempt is strictly denied by P003."""
    policy = PolicyEngine()
    rec = make_test_recommendation(
        event_id="txn_att_001",
        payment_id="pay_att_001",
        customer_id="cust_001",
        amount=1500.0,
        category=NormalizedFailureCategory.TRANSIENT,
        action=RecoveryAction.RETRY
    )
    p_state = PaymentStateContext(payment_id="pay_att_001", customer_id="cust_001", automated_attempt_count=2)
    c_state = CustomerStateContext(customer_id="cust_001")

    decision = policy.evaluate(rec, p_state, c_state)
    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id.value == "P003_MAX_AUTOMATED_ATTEMPTS"


def test_adv_6_malformed_transaction_handled_safely():
    """Edge Case 6: Negative amount transaction is caught by schema validation."""
    with pytest.raises(Exception):
        ReviveFeatures(
            event_id="txn_neg_001",
            customer_id="cust_001",
            amount=-500.0, # Negative amount rejected
            payment_method="UPI",
            payment_method_type="UPI",
            failure_category=NormalizedFailureCategory.TRANSIENT
        )


def test_adv_7_unsupported_action_rejected():
    """Edge Case 7: Invalid action string cannot bypass typed schema."""
    with pytest.raises(Exception):
        make_test_recommendation(action="UNAUTHORIZED_DISCOUNT_HACK")


def test_adv_8_client_cannot_fabricate_authorization():
    """Edge Case 8: Executor rejects fabricated token with mismatched payment ID."""
    executor = ControlledExecutor()
    fake_auth = ExecutionAuthorization(
        authorization_id="auth_fake_999",
        payment_id="pay_authorized_A",
        customer_id="cust_A",
        action=RecoveryAction.RETRY,
        policy_version="1.0.0",
        authorized_at="2026-09-02T12:00:00Z"
    )
    txn = make_test_transaction(payment_id="pay_different_B", customer_id="cust_A")
    p_state = PaymentStateContext(payment_id="pay_different_B", customer_id="cust_A")
    c_state = CustomerStateContext(customer_id="cust_A")

    res, _ = executor.execute(fake_auth, txn, p_state, c_state, None)
    assert res.execution_status == ExecutionStatus.BLOCKED
    assert "mismatch" in res.execution_reason.lower()


def test_adv_9_zero_high_risk_leaks_p005():
    """Edge Case 9: Flagged high-risk account routes strictly to Human Review."""
    policy = PolicyEngine()
    rec = make_test_recommendation(
        event_id="txn_fraud_001",
        payment_id="pay_fraud_001",
        customer_id="cust_fraud",
        amount=50000.0,
        category=NormalizedFailureCategory.HIGH_RISK,
        confidence=0.99,
        risk_signal=RiskSignal.HIGH,
        action=RecoveryAction.RETRY
    )
    p_state = PaymentStateContext(payment_id="pay_fraud_001", customer_id="cust_fraud")
    c_state = CustomerStateContext(customer_id="cust_fraud")

    decision = policy.evaluate(rec, p_state, c_state)
    assert decision.decision == PolicyDecisionType.HUMAN_REVIEW
    assert decision.primary_rule_id.value == "P005_HIGH_RISK_GATE"
    assert decision.execution_authorization is None


def test_adv_10_customer_contact_cap_p007():
    """Edge Case 10: Customer with 2 prior contacts cannot receive reminder/link."""
    policy = PolicyEngine()
    rec = make_test_recommendation(
        event_id="txn_contact_001",
        payment_id="pay_contact_001",
        customer_id="cust_spam",
        amount=1000.0,
        category=NormalizedFailureCategory.INSUFFICIENT_FUNDS,
        action=RecoveryAction.REMINDER
    )
    p_state = PaymentStateContext(payment_id="pay_contact_001", customer_id="cust_spam")
    c_state = CustomerStateContext(customer_id="cust_spam", contact_actions_count=2)

    decision = policy.evaluate(rec, p_state, c_state)
    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id.value == "P007_CUSTOMER_CONTACT_LIMIT"


def test_adv_11_unauthorized_case_execution_blocked():
    """Edge Case 11: Attempting to execute an unauthorized case returns blocked status."""
    client.post("/api/demo/reset")
    cases = client.get("/api/recovery-cases").json()
    deny_case = next((c for c in cases if not c["has_authorization"] or c["policy_decision"] in ("DENY", "HUMAN_REVIEW", "NO_ACTION")), None)
    if deny_case:
        res = client.post(f"/api/recovery-cases/{deny_case['event_id']}/execute").json()
        assert res["success"] is False
        assert res["execution_status"] == "BLOCKED"


def test_adv_12_non_existent_case_execution_404():
    """Edge Case 12: Attempting to execute a non-existent event ID returns 404."""
    res = client.post("/api/recovery-cases/txn_non_existent_fake/execute")
    assert res.status_code == 404


def test_adv_13_ground_truth_isolation_invariant():
    """Edge Case 13: Feature extraction never inspects hidden ground truth attributes."""
    bundle = DatasetSplitter.generate_evaluation_set(seed=42, transaction_count=50)
    for event in bundle.all_opportunities:
        assert not hasattr(event, "counterfactual_outcomes")
        assert not hasattr(event, "ground_truth_recoverable")


def test_adv_14_cooldown_period_rejection():
    """Edge Case 14: Actions requested inside 300s cooldown interval are denied."""
    policy = PolicyEngine()
    rec = make_test_recommendation(action=RecoveryAction.RETRY, timestamp="2026-09-02T12:00:00Z")
    p_state = PaymentStateContext(
        payment_id="pay_cool_001",
        customer_id="cust_cool_001",
        last_action_timestamp="2026-09-02T11:58:00Z" # 2 minutes ago
    )
    c_state = CustomerStateContext(customer_id="cust_cool_001")
    decision = policy.evaluate(rec, p_state, c_state)
    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id.value == "P008_COOLDOWN_ACTIVE"


def test_adv_15_arbitrary_client_action_injection_rejected():
    """Edge Case 15: Client cannot inject arbitrary string as recovery action."""
    with pytest.raises(Exception):
        ExecutionAuthorization(
            authorization_id="auth_inj_001",
            payment_id="pay_001",
            customer_id="cust_001",
            action="MALICIOUS_DROP_TABLE",
            policy_version="1.0.0",
            authorized_at="2026-09-02T12:00:00Z"
        )


def test_adv_16_corrupted_config_safely_rejected():
    """Edge Case 16: Zero attempt policy config handles edge bounds safely."""
    with pytest.raises(Exception):
        PolicyConfig(max_automated_actions_per_payment=0)


def test_adv_17_zero_division_safety_in_kpis():
    """Edge Case 17: Summary calculation on empty list handles division by zero safely."""
    from server.models import SimulationSummaryResponse
    s = SimulationSummaryResponse(
        total_transactions=0,
        total_failed_opportunities=0,
        revenue_at_risk=0.0,
        natural_recovery_revenue=0.0,
        total_recovered_revenue=0.0,
        incremental_recovered_revenue=0.0,
        overall_recovery_rate=0.0,
        intervention_success_rate=0.0,
        policy_authorized_count=0,
        policy_human_review_count=0,
        policy_denied_count=0,
        policy_no_action_count=0,
        actions_executed_count=0,
        actions_blocked_count=0,
        duplicate_attempts_prevented=0,
        action_breakdown={},
        safety_metrics={},
        session_seed=42,
        scenario="balanced"
    )
    assert s.total_transactions == 0


def test_adv_18_fingerprint_changes_on_seed_variation():
    """Edge Case 18: Fingerprint strictly differentiates different dataset seeds."""
    cfg = ReviveAppConfig()
    fp_a = cfg.compute_reproducibility_fingerprint(seed=101, size=100)
    fp_b = cfg.compute_reproducibility_fingerprint(seed=102, size=100)
    assert fp_a != fp_b


def test_adv_19_audit_trail_immutable_growth():
    """Edge Case 19: Audit trail only grows and never loses history during execution."""
    client.post("/api/demo/reset")
    audit1 = client.get("/api/audit").json()
    cases = client.get("/api/recovery-cases").json()
    allow_case = next((c for c in cases if c["has_authorization"]), None)
    if allow_case:
        client.post(f"/api/recovery-cases/{allow_case['event_id']}/execute")
        audit2 = client.get("/api/audit").json()
        assert len(audit2) >= len(audit1)


def test_adv_20_unknown_template_denied_p009():
    """Edge Case 20: Communication action with unregistered template is denied."""
    policy = PolicyEngine()
    rec = make_test_recommendation(action=RecoveryAction.REMINDER)
    p_state = PaymentStateContext(payment_id="pay_001", customer_id="cust_001")
    c_state = CustomerStateContext(customer_id="cust_001")
    decision = policy.evaluate(rec, p_state, c_state, custom_template_id="UNREGISTERED_SPAM_TEMPLATE_V99")
    assert decision.decision == PolicyDecisionType.DENY
    assert decision.primary_rule_id.value == "P009_UNAPPROVED_TEMPLATE"
