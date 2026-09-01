"""
Comprehensive automated unit, integration, and adversarial test suite for REVIVE Diagnosis & Recovery Scoring Engine.
Covers all Phase 4 requirements, domain edge cases, and performance invariants.
"""

import time
from pathlib import Path
import pytest

from agent.action_scorer import ActionScorer
from agent.diagnostician import DiagnosticsEngine
from agent.engine import ReviveEngine
from agent.features import FeatureExtractor
from agent.models import (
    NormalizedFailureCategory,
    RecoverabilityTier,
    RiskSignal,
)
from agent.recoverability import RecoverabilityScorer
from evaluation.pipeline import DatasetLoader
from simulator.enums import (
    CheckoutStage,
    CustomerProfile,
    CustomerSegment,
    ErrorReason,
    ErrorSource,
    ErrorStep,
    FailureCategory,
    PaymentMethod,
    PaymentMethodType,
    PaymentStatus,
    RecoveryAction,
)
from simulator.public_schema import (
    AbandonedCheckout,
    Customer,
    PaymentFailureDetails,
    Transaction,
)


@pytest.fixture
def reliable_customer():
    return Customer(
        customer_id="cust_000101",
        account_created_at="2025-06-01T00:00:00Z",
        customer_segment=CustomerSegment.CONSUMER_PRO,
        customer_profile=CustomerProfile.RELIABLE,
        customer_age_days=250,
        historical_transaction_count=25,
        historical_success_count=24,
        historical_failure_count=1,
        historical_success_rate=0.96,
        average_transaction_amount=1200.0,
        preferred_payment_method=PaymentMethod.UPI,
    )


@pytest.fixture
def chronic_failed_customer():
    return Customer(
        customer_id="cust_000102",
        account_created_at="2025-11-01T00:00:00Z",
        customer_segment=CustomerSegment.CONSUMER_RETAIL,
        customer_profile=CustomerProfile.HIGH_FAILURE,
        customer_age_days=60,
        historical_transaction_count=10,
        historical_success_count=2,
        historical_failure_count=8,
        historical_success_rate=0.20,
        average_transaction_amount=800.0,
        preferred_payment_method=PaymentMethod.CARD,
    )


@pytest.fixture
def new_customer():
    return Customer(
        customer_id="cust_000103",
        account_created_at="2026-01-10T00:00:00Z",
        customer_segment=CustomerSegment.CONSUMER_RETAIL,
        customer_profile=CustomerProfile.NEW_CUSTOMER,
        customer_age_days=3,
        historical_transaction_count=0,
        historical_success_count=0,
        historical_failure_count=0,
        historical_success_rate=1.0,
        average_transaction_amount=500.0,
        preferred_payment_method=PaymentMethod.UPI,
    )


def test_1_reliable_customer_isolated_timeout_high_recoverability(reliable_customer):
    """Test 1: Reliable customer + isolated timeout -> high recoverability (>= 0.70)."""
    txn = Transaction(
        transaction_id="txn_test_t1",
        payment_id="pay_test_t1",
        order_id="order_test_t1",
        customer_id=reliable_customer.customer_id,
        created_at="2026-01-15T12:00:00Z",
        amount=1200.0,
        currency="INR",
        payment_method=PaymentMethod.UPI,
        payment_method_type=PaymentMethodType.UPI_INTENT,
        status=PaymentStatus.FAILED,
        attempt_number=1,
        failure_details=PaymentFailureDetails(
            error_code="GATEWAY_ERROR_TIMEOUT",
            error_description="Timeout",
            error_source=ErrorSource.GATEWAY,
            error_step=ErrorStep.PAYMENT_PROCESSING,
            error_reason=ErrorReason.TIMEOUT,
            failure_category=FailureCategory.TRANSIENT_GATEWAY_FAILURE
        )
    )

    rec = ReviveEngine.evaluate(txn, reliable_customer)
    assert rec.recoverability_score >= 0.70
    assert rec.recoverability_tier == RecoverabilityTier.HIGH
    assert rec.diagnosis.category == NormalizedFailureCategory.TRANSIENT
    assert rec.recommended_action == RecoveryAction.RETRY


def test_2_repeated_hard_failure_low_recoverability(chronic_failed_customer):
    """Test 2: Repeated hard failure -> low recoverability (< 0.15)."""
    txn = Transaction(
        transaction_id="txn_test_t2",
        payment_id="pay_test_t2",
        order_id="order_test_t2",
        customer_id=chronic_failed_customer.customer_id,
        created_at="2026-01-15T12:00:00Z",
        amount=800.0,
        currency="INR",
        payment_method=PaymentMethod.CARD,
        payment_method_type=PaymentMethodType.DEBIT_CARD,
        status=PaymentStatus.FAILED,
        attempt_number=2,
        failure_details=PaymentFailureDetails(
            error_code="CARD_RESTRICTED_OR_BLOCKED",
            error_description="Blocked",
            error_source=ErrorSource.BANK,
            error_step=ErrorStep.PAYMENT_PROCESSING,
            error_reason=ErrorReason.PAYMENT_FAILED,
            failure_category=FailureCategory.HARD_FAILURE
        )
    )

    rec = ReviveEngine.evaluate(txn, chronic_failed_customer)
    assert rec.recoverability_score < 0.15
    assert rec.recoverability_tier == RecoverabilityTier.LOW
    assert rec.recommended_action == RecoveryAction.DO_NOTHING


def test_3_new_customer_uncertainty_handled_correctly(new_customer):
    """Test 3: New customer with zero history -> uncertainty expressed, no crash."""
    txn = Transaction(
        transaction_id="txn_test_t3",
        payment_id="pay_test_t3",
        order_id="order_test_t3",
        customer_id=new_customer.customer_id,
        created_at="2026-01-15T12:00:00Z",
        amount=500.0,
        currency="INR",
        payment_method=PaymentMethod.UPI,
        payment_method_type=PaymentMethodType.UPI_INTENT,
        status=PaymentStatus.FAILED,
        attempt_number=1,
        failure_details=PaymentFailureDetails(
            error_code="BAD_REQUEST_PAYMENT_DECLINED_BY_BANK",
            error_description="Declined",
            error_source=ErrorSource.BANK,
            error_step=ErrorStep.PAYMENT_AUTHORIZATION,
            error_reason=ErrorReason.PAYMENT_FAILED,
            failure_category=FailureCategory.BANK_DECLINE
        )
    )

    rec = ReviveEngine.evaluate(txn, new_customer)
    assert rec.diagnosis.confidence < 0.80 # Uncertainty penalty applied
    assert "NEW_CUSTOMER_LIMITED_HISTORY_PENALTY" in rec.diagnosis.reason_codes
    assert rec.recommended_action in (RecoveryAction.PAYMENT_LINK, RecoveryAction.DO_NOTHING)


def test_4_insufficient_funds_does_not_prefer_immediate_retry(reliable_customer):
    """Test 4: Insufficient funds -> Payment Link or Reminder preferred over Retry."""
    txn = Transaction(
        transaction_id="txn_test_t4",
        payment_id="pay_test_t4",
        order_id="order_test_t4",
        customer_id=reliable_customer.customer_id,
        created_at="2026-01-15T12:00:00Z",
        amount=1500.0,
        currency="INR",
        payment_method=PaymentMethod.UPI,
        payment_method_type=PaymentMethodType.UPI_INTENT,
        status=PaymentStatus.FAILED,
        attempt_number=1,
        failure_details=PaymentFailureDetails(
            error_code="BAD_REQUEST_PAYMENT_ACCOUNT_INSUFFICIENT_BALANCE",
            error_description="Low balance",
            error_source=ErrorSource.CUSTOMER,
            error_step=ErrorStep.PAYMENT_AUTHORIZATION,
            error_reason=ErrorReason.INSUFFICIENT_FUNDS,
            failure_category=FailureCategory.INSUFFICIENT_FUNDS
        )
    )

    rec = ReviveEngine.evaluate(txn, reliable_customer)
    ev_retry = rec.action_scores["RETRY"].expected_value
    ev_link = rec.action_scores["PAYMENT_LINK"].expected_value

    assert ev_link > ev_retry
    assert rec.recommended_action != RecoveryAction.RETRY
    assert rec.recommended_action == RecoveryAction.PAYMENT_LINK


def test_5_abandoned_otp_checkout_recommends_reminder(reliable_customer):
    """Test 5: Abandoned OTP checkout -> Reminder recommended."""
    chk = AbandonedCheckout(
        checkout_id="chk_test_t5",
        customer_id=reliable_customer.customer_id,
        created_at="2026-01-15T12:00:00Z",
        amount=1200.0,
        currency="INR",
        payment_method_selected=PaymentMethod.UPI,
        checkout_stage=CheckoutStage.OTP_STAGE,
        time_spent_seconds=90,
        is_abandoned=True
    )

    rec = ReviveEngine.evaluate(chk, reliable_customer)
    assert rec.recommended_action == RecoveryAction.REMINDER
    assert rec.recoverability_score >= 0.70


def test_6_high_risk_signal_triggers_human_review_or_block(reliable_customer):
    """Test 6: High-risk anomaly on significant amount triggers HUMAN_REVIEW."""
    txn = Transaction(
        transaction_id="txn_test_t6",
        payment_id="pay_test_t6",
        order_id="order_test_t6",
        customer_id=reliable_customer.customer_id,
        created_at="2026-01-15T12:00:00Z",
        amount=35000.0,
        currency="INR",
        payment_method=PaymentMethod.CARD,
        payment_method_type=PaymentMethodType.CREDIT_CARD,
        status=PaymentStatus.FAILED,
        attempt_number=1,
        failure_details=PaymentFailureDetails(
            error_code="GATEWAY_FRAUD_RISK_BLOCK",
            error_description="Risk block",
            error_source=ErrorSource.INTERNAL,
            error_step=ErrorStep.PAYMENT_PROCESSING,
            error_reason=ErrorReason.RISK_DETECTED,
            failure_category=FailureCategory.HIGH_RISK
        )
    )

    rec = ReviveEngine.evaluate(txn, reliable_customer)
    assert rec.diagnosis.risk_signal == RiskSignal.HIGH
    assert rec.recommended_action == RecoveryAction.HUMAN_REVIEW


def test_7_unknown_failure_graceful_low_confidence():
    """Test 7: Unclassified / missing failure diagnostics produces graceful low-confidence output."""
    txn = Transaction(
        transaction_id="txn_test_t7",
        payment_id="pay_test_t7",
        order_id="order_test_t7",
        customer_id="cust_unknown_01",
        created_at="2026-01-15T12:00:00Z",
        amount=500.0,
        currency="INR",
        payment_method=PaymentMethod.UPI,
        payment_method_type=PaymentMethodType.UPI_INTENT,
        status=PaymentStatus.FAILED,
        attempt_number=1,
        failure_details=None
    )

    rec = ReviveEngine.evaluate(txn, None)
    assert rec.diagnosis.category == NormalizedFailureCategory.UNKNOWN
    assert rec.diagnosis.confidence <= 0.40


def test_8_reproducible_deterministic_inference(reliable_customer):
    """Test 8: Same input evaluated multiple times produces exact bitwise identical recommendation."""
    txn = Transaction(
        transaction_id="txn_test_t8",
        payment_id="pay_test_t8",
        order_id="order_test_t8",
        customer_id=reliable_customer.customer_id,
        created_at="2026-01-15T12:00:00Z",
        amount=1500.0,
        currency="INR",
        payment_method=PaymentMethod.UPI,
        payment_method_type=PaymentMethodType.UPI_INTENT,
        status=PaymentStatus.FAILED,
        attempt_number=1,
        failure_details=PaymentFailureDetails(
            error_code="GATEWAY_ERROR_TIMEOUT",
            error_description="Timeout",
            error_source=ErrorSource.GATEWAY,
            error_step=ErrorStep.PAYMENT_PROCESSING,
            error_reason=ErrorReason.TIMEOUT,
            failure_category=FailureCategory.TRANSIENT_GATEWAY_FAILURE
        )
    )

    r1 = ReviveEngine.evaluate(txn, reliable_customer)
    r2 = ReviveEngine.evaluate(txn, reliable_customer)

    assert r1.recoverability_score == r2.recoverability_score
    assert r1.diagnosis.confidence == r2.diagnosis.confidence
    assert r1.recommended_action == r2.recommended_action
    assert r1.feature_contributions == r2.feature_contributions


def test_9_confidence_and_recoverability_are_distinct(chronic_failed_customer):
    """Test 9: Confident diagnosis of low-recoverability failure (Confidence != Recoverability)."""
    txn = Transaction(
        transaction_id="txn_test_t9",
        payment_id="pay_test_t9",
        order_id="order_test_t9",
        customer_id=chronic_failed_customer.customer_id,
        created_at="2026-01-15T12:00:00Z",
        amount=800.0,
        currency="INR",
        payment_method=PaymentMethod.CARD,
        payment_method_type=PaymentMethodType.DEBIT_CARD,
        status=PaymentStatus.FAILED,
        attempt_number=1,
        failure_details=PaymentFailureDetails(
            error_code="CARD_RESTRICTED_OR_BLOCKED",
            error_description="Blocked",
            error_source=ErrorSource.BANK,
            error_step=ErrorStep.PAYMENT_PROCESSING,
            error_reason=ErrorReason.PAYMENT_FAILED,
            failure_category=FailureCategory.HARD_FAILURE
        )
    )

    rec = ReviveEngine.evaluate(txn, chronic_failed_customer)
    assert rec.diagnosis.confidence >= 0.90 # High certainty about what happened
    assert rec.recoverability_score <= 0.10 # Low probability of recovering revenue


def test_10_recommendation_maximizes_expected_value(reliable_customer):
    """Test 10: Recommended action is strictly the action with highest Expected Value."""
    txn = Transaction(
        transaction_id="txn_test_t10",
        payment_id="pay_test_t10",
        order_id="order_test_t10",
        customer_id=reliable_customer.customer_id,
        created_at="2026-01-15T12:00:00Z",
        amount=2000.0,
        currency="INR",
        payment_method=PaymentMethod.UPI,
        payment_method_type=PaymentMethodType.UPI_INTENT,
        status=PaymentStatus.FAILED,
        attempt_number=1,
        failure_details=PaymentFailureDetails(
            error_code="GATEWAY_ERROR_TIMEOUT",
            error_description="Timeout",
            error_source=ErrorSource.GATEWAY,
            error_step=ErrorStep.PAYMENT_PROCESSING,
            error_reason=ErrorReason.TIMEOUT,
            failure_category=FailureCategory.TRANSIENT_GATEWAY_FAILURE
        )
    )

    rec = ReviveEngine.evaluate(txn, reliable_customer)
    max_ev = max(s.expected_value for s in rec.action_scores.values() if s.is_eligible)
    chosen_score = rec.action_scores[rec.recommended_action.value]

    assert chosen_score.expected_value == max_ev


# ------------------------------------------------------------------------------
# Adversarial & Edge Case Scenarios (Section 31)
# ------------------------------------------------------------------------------

def test_adversarial_high_value_anomaly(reliable_customer):
    """Adversarial Case D: High-Value Anomaly (Amount is 40x customer average)."""
    # Customer avg is 1200, current transaction is 50,000
    txn = Transaction(
        transaction_id="txn_adv_anomaly",
        payment_id="pay_adv_anomaly",
        order_id="order_adv_anomaly",
        customer_id=reliable_customer.customer_id,
        created_at="2026-01-15T12:00:00Z",
        amount=50000.0,
        currency="INR",
        payment_method=PaymentMethod.NETBANKING,
        payment_method_type=PaymentMethodType.NETBANKING_RETAIL,
        status=PaymentStatus.FAILED,
        attempt_number=1,
        failure_details=PaymentFailureDetails(
            error_code="BAD_REQUEST_PAYMENT_DECLINED_BY_BANK",
            error_description="Declined",
            error_source=ErrorSource.BANK,
            error_step=ErrorStep.PAYMENT_AUTHORIZATION,
            error_reason=ErrorReason.PAYMENT_FAILED,
            failure_category=FailureCategory.BANK_DECLINE
        )
    )

    rec = ReviveEngine.evaluate(txn, reliable_customer)
    # Amount anomaly triggers dampener in contributions and higher risk signal
    assert "amount_anomaly_dampener" in rec.feature_contributions
    assert any("higher than customer's average" in f for f in rec.top_negative_factors)
    # High value bank decline recommends HUMAN_REVIEW or PAYMENT_LINK
    assert rec.recommended_action in (RecoveryAction.HUMAN_REVIEW, RecoveryAction.PAYMENT_LINK)


def test_adversarial_subscription_mandate_expiry():
    """Adversarial Case: Subscription customer mandate expiry -> Payment Link with high stability score."""
    sub_cust = Customer(
        customer_id="cust_sub_01",
        account_created_at="2025-01-01T00:00:00Z",
        customer_segment=CustomerSegment.CONSUMER_PRO,
        customer_profile=CustomerProfile.SUBSCRIPTION,
        customer_age_days=365,
        historical_transaction_count=12,
        historical_success_count=11,
        historical_failure_count=1,
        historical_success_rate=0.9167,
        average_transaction_amount=999.0,
        preferred_payment_method=PaymentMethod.CARD,
    )

    txn = Transaction(
        transaction_id="txn_sub_exp",
        payment_id="pay_sub_exp",
        order_id="order_sub_exp",
        customer_id=sub_cust.customer_id,
        created_at="2026-01-15T12:00:00Z",
        amount=999.0,
        currency="INR",
        payment_method=PaymentMethod.CARD,
        payment_method_type=PaymentMethodType.CREDIT_CARD,
        status=PaymentStatus.FAILED,
        attempt_number=1,
        failure_details=PaymentFailureDetails(
            error_code="BAD_REQUEST_PAYMENT_CARD_EXPIRED",
            error_description="Card expired",
            error_source=ErrorSource.CUSTOMER,
            error_step=ErrorStep.PAYMENT_PROCESSING,
            error_reason=ErrorReason.PAYMENT_METHOD_FAILED,
            failure_category=FailureCategory.PAYMENT_METHOD_FAILURE
        )
    )

    rec = ReviveEngine.evaluate(txn, sub_cust)
    assert rec.diagnosis.category == NormalizedFailureCategory.PAYMENT_METHOD
    assert rec.recommended_action == RecoveryAction.PAYMENT_LINK
    assert "subscription_stability" in rec.feature_contributions


def test_performance_batch_processing():
    """Performance Test: Batch processes 2,000+ opportunities in under 5.0 seconds."""
    data_dir = Path("data")
    customers_by_id, transactions, checkouts, _ = DatasetLoader.load(data_dir)

    failed_txns = [t for t in transactions if t.status == PaymentStatus.FAILED]
    all_ops = failed_txns + checkouts

    t0 = time.perf_counter()
    recs, summary = ReviveEngine.evaluate_batch(all_ops, customers_by_id)
    t1 = time.perf_counter()

    elapsed = t1 - t0
    assert len(recs) == len(all_ops)
    assert elapsed < 5.0, f"Batch processing took {elapsed:.2f}s (expected < 5.0s)"
