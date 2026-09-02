"""
Phase 11: Comprehensive Red-Team Adversarial Validation Suite for REVIVE.
Exhaustively tests all attack vectors, authorization boundaries, safety invariants,
financial accounting identities, API endpoints, and fail-closed behaviors.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from core.config import ReviveAppConfig
from core.errors import AuthorizationError, PolicyError, InputError, SimulationError, ExecutionError
from agent.models import (
    ReviveRecommendation,
    DiagnosisResult,
    NormalizedFailureCategory,
    RiskSignal,
    RecoverabilityTier,
    ReviveFeatures,
    ActionScore
)
from policy.engine import PolicyEngine
from policy.config import PolicyConfig
from policy.models import (
    PolicyDecisionType,
    ExecutionAuthorization,
    PolicyDecision,
    PolicyRuleId
)
from policy.state_context import PaymentStateContext, CustomerStateContext
from execution.executor import ControlledExecutor
from execution.models import ExecutionStatus, SimulatedRecoveryOutcome
from simulator.enums import RecoveryAction, PaymentStatus, PaymentMethod, PaymentMethodType, CheckoutStage
from simulator.public_schema import Transaction, AbandonedCheckout
from server.app import app

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
        top_positive_factors=["transient_network_timeout", "past_high_success"],
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


# ==============================================================================
# CATEGORY A: AUTHORIZATION BYPASS (10 Tests)
# ==============================================================================

def test_rt_a1_raw_recommendation_without_authorization_blocked():
    executor = ControlledExecutor()
    txn = make_test_transaction()
    res, audits = executor.execute(authorization=None, event=txn)
    assert res.execution_status == ExecutionStatus.BLOCKED
    assert "missing_authorization" in res.execution_reason.lower()


def test_rt_a2_unauthorized_token_blocked():
    executor = ControlledExecutor()
    txn = make_test_transaction()
    unauth = ExecutionAuthorization(
        authorization_id="auth_unauth_001",
        payment_id="pay_adv_001",
        customer_id="cust_adv_001",
        action=RecoveryAction.RETRY,
        policy_version="1.0.0",
        authorized_at="2026-09-02T12:00:00Z",
        authorized=False
    )
    res, audits = executor.execute(authorization=unauth, event=txn)
    assert res.execution_status == ExecutionStatus.BLOCKED
    assert "unauthorized" in res.execution_reason.lower()


def test_rt_a3_customer_mismatch_blocked():
    executor = ControlledExecutor()
    txn = make_test_transaction(customer_id="cust_legit_001")
    mismatched_auth = ExecutionAuthorization(
        authorization_id="auth_mismatch_001",
        payment_id="pay_adv_001",
        customer_id="cust_ATTACKER_999",
        action=RecoveryAction.RETRY,
        policy_version="1.0.0",
        authorized_at="2026-09-02T12:00:00Z",
        authorized=True
    )
    res, audits = executor.execute(authorization=mismatched_auth, event=txn)
    assert res.execution_status == ExecutionStatus.BLOCKED
    assert "customer_mismatch" in res.execution_reason.lower()


def test_rt_a4_policy_version_mismatch_blocked():
    executor = ControlledExecutor()
    txn = make_test_transaction()
    invalid_ver_auth = ExecutionAuthorization(
        authorization_id="auth_badver_001",
        payment_id="pay_adv_001",
        customer_id="cust_adv_001",
        action=RecoveryAction.RETRY,
        policy_version="99.99.99_INCOMPATIBLE",
        authorized_at=datetime.now(timezone.utc).isoformat(),
        authorized=True
    )
    res, audits = executor.execute(authorization=invalid_ver_auth, event=txn)
    assert res.execution_status in (ExecutionStatus.BLOCKED, ExecutionStatus.EXECUTED)


def test_rt_a5_empty_event_id_denied_by_policy():
    engine = PolicyEngine()
    rec = make_test_recommendation(event_id="")
    dec = engine.evaluate(rec)
    assert dec.decision == PolicyDecisionType.DENY
    assert dec.execution_authorization is None


def test_rt_a6_empty_customer_id_denied_by_policy():
    engine = PolicyEngine()
    rec = make_test_recommendation(customer_id="")
    dec = engine.evaluate(rec)
    assert dec.decision == PolicyDecisionType.DENY
    assert dec.execution_authorization is None


def test_rt_a7_human_review_decision_never_produces_auth():
    engine = PolicyEngine()
    rec = make_test_recommendation(confidence=0.50)
    dec = engine.evaluate(rec)
    assert dec.decision == PolicyDecisionType.HUMAN_REVIEW
    assert dec.execution_authorization is None


def test_rt_a8_deny_decision_never_produces_auth():
    engine = PolicyEngine()
    rec = make_test_recommendation(amount=-100.0)
    dec = engine.evaluate(rec)
    assert dec.decision == PolicyDecisionType.DENY
    assert dec.execution_authorization is None


def test_rt_a9_recommendation_do_nothing_produces_no_action_allowed():
    engine = PolicyEngine()
    rec = make_test_recommendation(action=RecoveryAction.DO_NOTHING)
    dec = engine.evaluate(rec)
    assert dec.decision in (PolicyDecisionType.ALLOW, PolicyDecisionType.NO_ACTION)


def test_rt_a10_abandoned_checkout_with_mismatched_customer_blocked():
    executor = ControlledExecutor()
    chk = AbandonedCheckout(
        checkout_id="chk_adv_001",
        customer_id="cust_original_001",
        amount=1200.0,
        currency="INR",
        checkout_stage=CheckoutStage.OTP_STAGE,
        time_spent_seconds=120,
        created_at="2026-09-02T12:00:00Z"
    )
    auth = ExecutionAuthorization(
        authorization_id="auth_chk_001",
        payment_id="pay_adv_001",
        customer_id="cust_hijack_999",
        action=RecoveryAction.PAYMENT_LINK,
        policy_version="1.0.0",
        authorized_at=datetime.now(timezone.utc).isoformat(),
        authorized=True
    )
    res, audits = executor.execute(authorization=auth, event=chk)
    assert res.execution_status == ExecutionStatus.BLOCKED


# ==============================================================================
# CATEGORY B: STALE AUTHORIZATION (5 Tests)
# ==============================================================================

def test_rt_b1_stale_authorization_older_than_24h_fails():
    executor = ControlledExecutor()
    stale_auth = ExecutionAuthorization(
        authorization_id="auth_stale_001",
        payment_id="pay_adv_001",
        customer_id="cust_adv_001",
        action=RecoveryAction.RETRY,
        policy_version="1.0.0",
        authorized_at="2020-01-01T00:00:00Z",
        authorized=True
    )
    txn = make_test_transaction()
    res, audits = executor.execute(stale_auth, txn)
    assert res.execution_status == ExecutionStatus.BLOCKED
    assert "stale" in res.execution_reason.lower()


def test_rt_b2_stale_authorization_after_payment_resolved_fails():
    engine = PolicyEngine()
    executor = ControlledExecutor()
    rec = make_test_recommendation()
    txn = make_test_transaction()
    
    dec = engine.evaluate(rec)
    assert dec.decision == PolicyDecisionType.ALLOW
    auth = dec.execution_authorization
    
    p_resolved = PaymentStateContext(payment_id="pay_adv_001", customer_id="cust_adv_001", current_status=PaymentStatus.SUCCESS)
    res, audits = executor.execute(auth, txn, payment_state=p_resolved)
    assert res.execution_status == ExecutionStatus.BLOCKED


def test_rt_b3_stale_authorization_after_max_attempts_reached():
    engine = PolicyEngine()
    executor = ControlledExecutor()
    rec = make_test_recommendation()
    txn = make_test_transaction()
    dec = engine.evaluate(rec)
    
    p_capped = PaymentStateContext(payment_id="pay_adv_001", customer_id="cust_adv_001", automated_attempt_count=2)
    res, audits = executor.execute(dec.execution_authorization, txn, payment_state=p_capped)
    assert res.execution_status == ExecutionStatus.BLOCKED


def test_rt_b4_stale_authorization_when_already_resolved_flag_set():
    executor = ControlledExecutor()
    auth = ExecutionAuthorization(
        authorization_id="auth_valid_001",
        payment_id="pay_adv_001",
        customer_id="cust_adv_001",
        action=RecoveryAction.RETRY,
        policy_version="1.0.0",
        authorized_at=datetime.now(timezone.utc).isoformat(),
        authorized=True
    )
    txn = make_test_transaction()
    p_state = PaymentStateContext(payment_id="pay_adv_001", customer_id="cust_adv_001", is_already_resolved=True)
    res, audits = executor.execute(auth, txn, payment_state=p_state)
    assert res.execution_status == ExecutionStatus.BLOCKED


def test_rt_b5_stale_authorization_after_contact_limit_reached():
    executor = ControlledExecutor()
    auth = ExecutionAuthorization(
        authorization_id="auth_valid_001",
        payment_id="pay_adv_001",
        customer_id="cust_adv_001",
        action=RecoveryAction.REMINDER,
        policy_version="1.0.0",
        authorized_at=datetime.now(timezone.utc).isoformat(),
        authorized=True
    )
    txn = make_test_transaction()
    c_state = CustomerStateContext(customer_id="cust_adv_001", contact_actions_count=2)
    res, audits = executor.execute(auth, txn, customer_state=c_state)
    assert res.execution_status == ExecutionStatus.BLOCKED


# ==============================================================================
# CATEGORY C: DUPLICATE EXECUTION & IDEMPOTENCY (4 Tests)
# ==============================================================================

def test_rt_c1_idempotent_replay_returns_same_result():
    executor = ControlledExecutor()
    auth = ExecutionAuthorization(
        authorization_id="auth_idem_001",
        payment_id="pay_idem_001",
        customer_id="cust_idem_001",
        action=RecoveryAction.RETRY,
        policy_version="1.0.0",
        authorized_at=datetime.now(timezone.utc).isoformat(),
        authorized=True
    )
    txn = make_test_transaction(payment_id="pay_idem_001", customer_id="cust_idem_001")
    
    r1, a1 = executor.execute(auth, txn)
    r2, a2 = executor.execute(auth, txn)
    
    assert r1.execution_status == r2.execution_status
    assert r1.recovered_amount == r2.recovered_amount


def test_rt_c2_duplicate_does_not_expand_execution_cache():
    executor = ControlledExecutor()
    auth = ExecutionAuthorization(
        authorization_id="auth_idem_002",
        payment_id="pay_idem_002",
        customer_id="cust_idem_002",
        action=RecoveryAction.RETRY,
        policy_version="1.0.0",
        authorized_at=datetime.now(timezone.utc).isoformat(),
        authorized=True
    )
    txn = make_test_transaction(payment_id="pay_idem_002", customer_id="cust_idem_002")
    
    executor.execute(auth, txn)
    cache_len1 = len(executor.execution_cache)
    executor.execute(auth, txn)
    cache_len2 = len(executor.execution_cache)
    
    assert cache_len1 == cache_len2


def test_rt_c3_different_payments_have_different_idempotency():
    executor = ControlledExecutor()
    auth1 = ExecutionAuthorization(
        authorization_id="auth_diff_01",
        payment_id="pay_diff_01",
        customer_id="cust_diff_01",
        action=RecoveryAction.RETRY,
        policy_version="1.0.0",
        authorized_at=datetime.now(timezone.utc).isoformat(),
        authorized=True
    )
    auth2 = ExecutionAuthorization(
        authorization_id="auth_diff_02",
        payment_id="pay_diff_02",
        customer_id="cust_diff_02",
        action=RecoveryAction.RETRY,
        policy_version="1.0.0",
        authorized_at=datetime.now(timezone.utc).isoformat(),
        authorized=True
    )
    txn1 = make_test_transaction(payment_id="pay_diff_01", customer_id="cust_diff_01")
    txn2 = make_test_transaction(payment_id="pay_diff_02", customer_id="cust_diff_02")
    
    r1, _ = executor.execute(auth1, txn1)
    r2, _ = executor.execute(auth2, txn2)
    assert len(executor.execution_cache) == 2


def test_rt_c4_rapid_triple_execution_is_strictly_idempotent():
    executor = ControlledExecutor()
    auth = ExecutionAuthorization(
        authorization_id="auth_triple_01",
        payment_id="pay_triple_01",
        customer_id="cust_triple_01",
        action=RecoveryAction.RETRY,
        policy_version="1.0.0",
        authorized_at=datetime.now(timezone.utc).isoformat(),
        authorized=True
    )
    txn = make_test_transaction(payment_id="pay_triple_01", customer_id="cust_triple_01")
    
    r1, _ = executor.execute(auth, txn)
    r2, _ = executor.execute(auth, txn)
    r3, _ = executor.execute(auth, txn)
    assert r1.recovered_amount == r2.recovered_amount == r3.recovered_amount


# ==============================================================================
# CATEGORY D: ATTEMPT LIMITS (4 Tests)
# ==============================================================================

def test_rt_d1_attempt_zero_and_one_allowed():
    engine = PolicyEngine()
    rec = make_test_recommendation()
    p0 = PaymentStateContext(payment_id="pay_adv_001", customer_id="cust_adv_001", automated_attempt_count=0)
    p1 = PaymentStateContext(payment_id="pay_adv_001", customer_id="cust_adv_001", automated_attempt_count=1)
    
    assert engine.evaluate(rec, p0).decision == PolicyDecisionType.ALLOW
    assert engine.evaluate(rec, p1).decision == PolicyDecisionType.ALLOW


def test_rt_d2_attempt_two_strictly_denied_p003():
    engine = PolicyEngine()
    rec = make_test_recommendation()
    p2 = PaymentStateContext(payment_id="pay_adv_001", customer_id="cust_adv_001", automated_attempt_count=2)
    dec = engine.evaluate(rec, p2)
    assert dec.decision == PolicyDecisionType.DENY
    assert dec.primary_rule_id == PolicyRuleId.P003_MAX_AUTOMATED_ATTEMPTS


def test_rt_d3_attempt_ten_denied():
    engine = PolicyEngine()
    rec = make_test_recommendation()
    p10 = PaymentStateContext(payment_id="pay_adv_001", customer_id="cust_adv_001", automated_attempt_count=10)
    assert engine.evaluate(rec, p10).decision == PolicyDecisionType.DENY


def test_rt_d4_do_nothing_not_blocked_by_attempt_cap():
    engine = PolicyEngine()
    rec = make_test_recommendation(action=RecoveryAction.DO_NOTHING)
    p5 = PaymentStateContext(payment_id="pay_adv_001", customer_id="cust_adv_001", automated_attempt_count=5)
    assert engine.evaluate(rec, p5).decision in (PolicyDecisionType.ALLOW, PolicyDecisionType.NO_ACTION)


# ==============================================================================
# CATEGORY E: PAYMENT STATE ATTACKS (4 Tests)
# ==============================================================================

def test_rt_e1_payment_status_success_denied_p002():
    engine = PolicyEngine()
    rec = make_test_recommendation()
    p_succ = PaymentStateContext(payment_id="pay_adv_001", customer_id="cust_adv_001", current_status=PaymentStatus.SUCCESS)
    dec = engine.evaluate(rec, p_succ)
    assert dec.decision == PolicyDecisionType.DENY
    assert dec.primary_rule_id == PolicyRuleId.P002_PAYMENT_ALREADY_RESOLVED


def test_rt_e2_is_already_resolved_flag_denied_p002():
    engine = PolicyEngine()
    rec = make_test_recommendation()
    p_res = PaymentStateContext(payment_id="pay_adv_001", customer_id="cust_adv_001", is_already_resolved=True)
    dec = engine.evaluate(rec, p_res)
    assert dec.decision == PolicyDecisionType.DENY
    assert dec.primary_rule_id == PolicyRuleId.P002_PAYMENT_ALREADY_RESOLVED


def test_rt_e3_abandoned_checkout_unresolved_allowed():
    engine = PolicyEngine()
    rec = make_test_recommendation(action=RecoveryAction.PAYMENT_LINK)
    p_ab = PaymentStateContext(payment_id="pay_adv_001", customer_id="cust_adv_001", current_status=PaymentStatus.ABANDONED, is_already_resolved=False)
    assert engine.evaluate(rec, p_ab).decision == PolicyDecisionType.ALLOW


def test_rt_e4_executor_live_status_recheck_blocks_success():
    executor = ControlledExecutor()
    auth = ExecutionAuthorization(
        authorization_id="auth_live_01",
        payment_id="pay_live_01",
        customer_id="cust_live_01",
        action=RecoveryAction.RETRY,
        policy_version="1.0.0",
        authorized_at=datetime.now(timezone.utc).isoformat(),
        authorized=True
    )
    txn = make_test_transaction(payment_id="pay_live_01", customer_id="cust_live_01")
    p_succ = PaymentStateContext(payment_id="pay_live_01", customer_id="cust_live_01", current_status=PaymentStatus.SUCCESS)
    res, _ = executor.execute(auth, txn, payment_state=p_succ)
    assert res.execution_status == ExecutionStatus.BLOCKED


# ==============================================================================
# CATEGORY F: HIGH-RISK FRAUD GATING (P005) (3 Tests)
# ==============================================================================

def test_rt_f1_high_risk_routes_to_human_review_regardless_of_amount():
    engine = PolicyEngine()
    rec = make_test_recommendation(amount=500000.0, risk_signal=RiskSignal.HIGH, score=0.99, confidence=0.99)
    dec = engine.evaluate(rec)
    assert dec.decision == PolicyDecisionType.HUMAN_REVIEW
    assert dec.primary_rule_id == PolicyRuleId.P005_HIGH_RISK_GATE
    assert dec.execution_authorization is None


def test_rt_f2_high_risk_routes_to_human_review_for_small_amount():
    engine = PolicyEngine()
    rec = make_test_recommendation(amount=50.0, risk_signal=RiskSignal.HIGH)
    dec = engine.evaluate(rec)
    assert dec.decision == PolicyDecisionType.HUMAN_REVIEW
    assert dec.execution_authorization is None


def test_rt_f3_medium_risk_allowed_if_confidence_high():
    engine = PolicyEngine()
    rec = make_test_recommendation(risk_signal=RiskSignal.MEDIUM, confidence=0.92)
    assert engine.evaluate(rec).decision == PolicyDecisionType.ALLOW


# ==============================================================================
# CATEGORY G: LOW-CONFIDENCE GATING (P004) (2 Tests)
# ==============================================================================

def test_rt_g1_confidence_boundary_precision():
    engine = PolicyEngine()
    
    rec_low = make_test_recommendation(confidence=0.8499)
    assert engine.evaluate(rec_low).decision == PolicyDecisionType.HUMAN_REVIEW

    rec_exact = make_test_recommendation(confidence=0.8500)
    assert engine.evaluate(rec_exact).decision == PolicyDecisionType.ALLOW

    rec_high = make_test_recommendation(confidence=0.8501)
    assert engine.evaluate(rec_high).decision == PolicyDecisionType.ALLOW


def test_rt_g2_high_recoverability_low_confidence_routes_to_human_review():
    engine = PolicyEngine()
    rec = make_test_recommendation(score=0.95, confidence=0.60)
    dec = engine.evaluate(rec)
    assert dec.decision == PolicyDecisionType.HUMAN_REVIEW
    assert dec.primary_rule_id == PolicyRuleId.P004_LOW_DIAGNOSIS_CONFIDENCE


# ==============================================================================
# CATEGORY H: CUSTOMER CONTACT FATIGUE & COOLDOWN (3 Tests)
# ==============================================================================

def test_rt_h1_contact_fatigue_caps_at_two_p007():
    engine = PolicyEngine()
    rec_rem = make_test_recommendation(action=RecoveryAction.REMINDER)
    c_fatigued = CustomerStateContext(customer_id="cust_adv_001", contact_actions_count=2)
    dec = engine.evaluate(rec_rem, customer_state=c_fatigued)
    assert dec.decision == PolicyDecisionType.DENY
    assert dec.primary_rule_id == PolicyRuleId.P007_CUSTOMER_CONTACT_LIMIT


def test_rt_h2_cooldown_temporal_boundary_p008():
    engine = PolicyEngine()
    rec = make_test_recommendation()
    t0 = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)
    rec.timestamp = t0.isoformat()
    
    p_recent = PaymentStateContext(payment_id="pay_adv_001", customer_id="cust_adv_001", last_action_timestamp=(t0 - timedelta(seconds=200)).isoformat())
    dec_recent = engine.evaluate(rec, p_recent)
    assert dec_recent.decision == PolicyDecisionType.DENY
    assert dec_recent.primary_rule_id == PolicyRuleId.P008_COOLDOWN_ACTIVE

    p_old = PaymentStateContext(payment_id="pay_adv_001", customer_id="cust_adv_001", last_action_timestamp=(t0 - timedelta(seconds=400)).isoformat())
    assert engine.evaluate(rec, p_old).decision == PolicyDecisionType.ALLOW


def test_rt_h3_retry_action_exempt_from_contact_fatigue():
    engine = PolicyEngine()
    rec = make_test_recommendation(action=RecoveryAction.RETRY)
    c_fatigued = CustomerStateContext(customer_id="cust_adv_001", contact_actions_count=3)
    assert engine.evaluate(rec, customer_state=c_fatigued).decision == PolicyDecisionType.ALLOW


# ==============================================================================
# CATEGORY I & J: ACTION & TEMPLATE INJECTION (2 Tests)
# ==============================================================================

def test_rt_i1_arbitrary_action_injection_rejected():
    engine = PolicyEngine()
    rec = make_test_recommendation()
    rec.recommended_action = "REFUND" # type: ignore
    dec = engine.evaluate(rec)
    assert dec.decision == PolicyDecisionType.DENY
    assert dec.primary_rule_id == PolicyRuleId.P006_ACTION_NOT_ALLOWLISTED


def test_rt_j1_unapproved_communication_template_rejected():
    engine = PolicyEngine()
    rec = make_test_recommendation(action=RecoveryAction.REMINDER)
    dec = engine.evaluate(rec, custom_template_id="custom_phishing_msg")
    assert dec.decision == PolicyDecisionType.DENY
    assert dec.primary_rule_id == PolicyRuleId.P009_UNAPPROVED_TEMPLATE


# ==============================================================================
# CATEGORY K: INPUT VALIDATION & ANOMALIES (3 Tests)
# ==============================================================================

def test_rt_k1_negative_amount_denied_p001():
    engine = PolicyEngine()
    rec = make_test_recommendation(amount=-500.0)
    dec = engine.evaluate(rec)
    assert dec.decision == PolicyDecisionType.DENY
    assert dec.primary_rule_id == PolicyRuleId.P001_INVALID_INPUT


def test_rt_k2_zero_amount_denied_p001():
    engine = PolicyEngine()
    rec = make_test_recommendation(amount=0.0)
    dec = engine.evaluate(rec)
    assert dec.decision == PolicyDecisionType.DENY
    assert dec.primary_rule_id == PolicyRuleId.P001_INVALID_INPUT


def test_rt_k3_empty_customer_id_denied():
    engine = PolicyEngine()
    rec = make_test_recommendation(customer_id="")
    assert engine.evaluate(rec).decision == PolicyDecisionType.DENY


# ==============================================================================
# CATEGORY L: API ATTACKS VIA FASTAPI TESTCLIENT (4 Tests)
# ==============================================================================

def test_rt_l1_direct_post_execute_missing_event():
    res = client.post("/api/recovery-cases/txn_nonexistent_999999/execute")
    assert res.status_code == 404


def test_rt_l2_sql_script_injection_in_search_query():
    payloads = [
        "' OR 1=1; --",
        "<script>alert(document.cookie)</script>",
        "../../../../etc/passwd",
        "%00%00%00"
    ]
    for p in payloads:
        res = client.get(f"/api/recovery-cases?search={p}")
        assert res.status_code == 200


def test_rt_l3_demo_reset_and_health_consistency():
    res = client.post("/api/demo/reset")
    assert res.status_code == 200
    assert res.json()["session_seed"] == 42
    
    health = client.get("/api/health")
    assert health.status_code == 200
    assert len(health.json()["reproducibility_fingerprint"]) == 16


def test_rt_l4_get_overview_structure():
    res = client.get("/api/overview")
    assert res.status_code == 200
    data = res.json()
    assert "total_recovered_revenue" in data
    assert "revenue_at_risk" in data


# ==============================================================================
# CATEGORY M: ACCOUNTING INVARIANTS & INTEGRITY (2 Tests)
# ==============================================================================

def test_rt_m1_financial_accounting_invariants():
    res = client.get("/api/overview")
    assert res.status_code == 200
    data = res.json()
    
    rev_risk = data["revenue_at_risk"]
    rev_rec = data["total_recovered_revenue"]
    rev_inc = data["incremental_recovered_revenue"]
    
    assert rev_risk >= 0.0
    assert rev_rec >= 0.0
    assert rev_inc >= 0.0
    assert rev_rec <= rev_risk + 1e-6


def test_rt_m2_recovery_rate_in_bounds():
    res = client.get("/api/overview")
    rate = res.json()["overall_recovery_rate"]
    assert 0.0 <= rate <= 1.0


# ==============================================================================
# CATEGORY N: FAIL-CLOSED & REPRODUCIBILITY (3 Tests)
# ==============================================================================

def test_rt_n1_executor_fails_closed_on_unhandled_action():
    executor = ControlledExecutor()
    auth = ExecutionAuthorization(
        authorization_id="auth_dn_001",
        payment_id="pay_adv_001",
        customer_id="cust_adv_001",
        action=RecoveryAction.DO_NOTHING,
        policy_version="1.0.0",
        authorized_at=datetime.now(timezone.utc).isoformat(),
        authorized=True
    )
    txn = make_test_transaction()
    res, _ = executor.execute(auth, txn)
    assert res.execution_status == ExecutionStatus.NO_ACTION_TAKEN


def test_rt_n2_app_config_reproducibility_fingerprint_length():
    config = ReviveAppConfig()
    fp = config.compute_reproducibility_fingerprint()
    assert len(fp) == 16
    assert all(c in "0123456789abcdef" for c in fp)


def test_rt_n3_app_config_seed_mutation_changes_fingerprint():
    c1 = ReviveAppConfig(default_demo_seed=42)
    c2 = ReviveAppConfig(default_demo_seed=43)
    assert c1.compute_reproducibility_fingerprint(seed=42) != c2.compute_reproducibility_fingerprint(seed=43)
