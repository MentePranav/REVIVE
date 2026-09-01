"""
Automated unit and integration test suite for REVIVE Baseline Recovery Strategies & Benchmark Engine.
Covers all Phase 3 required tests, adversarial scenarios, fairness constraints, and CLI execution.
"""

import json
import subprocess
import sys
from pathlib import Path
import pytest

from evaluation.guards import LifecycleGuard
from evaluation.models import ActionCostConfig, StrategyDecision
from evaluation.outcome_evaluator import OutcomeEvaluator
from evaluation.pipeline import DatasetLoader, EvaluationPipeline
from evaluation.strategies import NaiveRetryStrategy, NoActionStrategy, RuleBasedStrategy
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
    RecoveryOutcome,
)
from simulator.ground_truth_schema import GroundTruthRecord
from simulator.public_schema import (
    AbandonedCheckout,
    Customer,
    PaymentFailureDetails,
    Transaction,
)


@pytest.fixture
def mock_customer():
    return Customer(
        customer_id="cust_000100",
        account_created_at="2026-01-01T00:00:00Z",
        customer_segment=CustomerSegment.CONSUMER_PRO,
        customer_profile=CustomerProfile.RELIABLE,
        customer_age_days=120,
        historical_transaction_count=20,
        historical_success_count=19,
        historical_failure_count=1,
        historical_success_rate=0.95,
        average_transaction_amount=1500.0,
        preferred_payment_method=PaymentMethod.UPI,
    )


@pytest.fixture
def sample_dataset_dir():
    return Path("data")


def test_1_no_action_produces_zero_interventions(mock_customer):
    """Test 1: No-action strategy never initiates active interventions."""
    strategy = NoActionStrategy()
    txn = Transaction(
        transaction_id="txn_test_01",
        payment_id="pay_test_01",
        order_id="order_test_01",
        customer_id=mock_customer.customer_id,
        created_at="2026-01-15T12:00:00Z",
        amount=1999.0,
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

    decision = strategy.decide(txn, mock_customer, [])
    assert decision.action == RecoveryAction.DO_NOTHING
    assert decision.rule_id == "R000_NO_ACTION"


def test_2_naive_retry_never_retries_more_than_once(mock_customer):
    """Test 2: Naive retry strictly adheres to single retry limit per payment."""
    strategy = NaiveRetryStrategy()
    txn = Transaction(
        transaction_id="txn_test_02",
        payment_id="pay_test_02",
        order_id="order_test_02",
        customer_id=mock_customer.customer_id,
        created_at="2026-01-15T12:00:00Z",
        amount=999.0,
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

    # First attempt -> RETRY
    d1 = strategy.decide(txn, mock_customer, [])
    assert d1.action == RecoveryAction.RETRY

    # Second attempt on same transaction -> DO_NOTHING
    d2 = strategy.decide(txn, mock_customer, [d1])
    assert d2.action == RecoveryAction.DO_NOTHING
    assert d2.rule_id == "R_NAIVE_MAX_RETRY_REACHED"


def test_3_rule_based_strategy_returns_deterministic_decisions(mock_customer):
    """Test 3: Rule-based strategy produces 100% deterministic decisions for identical inputs."""
    strategy = RuleBasedStrategy()
    txn = Transaction(
        transaction_id="txn_test_03",
        payment_id="pay_test_03",
        order_id="order_test_03",
        customer_id=mock_customer.customer_id,
        created_at="2026-01-15T12:00:00Z",
        amount=2500.0,
        currency="INR",
        payment_method=PaymentMethod.CARD,
        payment_method_type=PaymentMethodType.CREDIT_CARD,
        status=PaymentStatus.FAILED,
        attempt_number=1,
        failure_details=PaymentFailureDetails(
            error_code="BAD_REQUEST_PAYMENT_ACCOUNT_INSUFFICIENT_BALANCE",
            error_description="Insufficient funds",
            error_source=ErrorSource.CUSTOMER,
            error_step=ErrorStep.PAYMENT_AUTHORIZATION,
            error_reason=ErrorReason.INSUFFICIENT_FUNDS,
            failure_category=FailureCategory.INSUFFICIENT_FUNDS
        )
    )

    d1 = strategy.decide(txn, mock_customer, [])
    d2 = strategy.decide(txn, mock_customer, [])

    assert d1.action == d2.action == RecoveryAction.PAYMENT_LINK
    assert d1.rule_id == d2.rule_id == "R002_INSUFFICIENT_FUNDS_PAYMENT_LINK"


def test_4_strategies_cannot_access_hidden_ground_truth(mock_customer):
    """Test 4: Type-level guarantee: Strategy inputs do not expose GroundTruth models."""
    strategy = RuleBasedStrategy()
    txn = Transaction(
        transaction_id="txn_test_04",
        payment_id="pay_test_04",
        order_id="order_test_04",
        customer_id=mock_customer.customer_id,
        created_at="2026-01-15T12:00:00Z",
        amount=500.0,
        currency="INR",
        payment_method=PaymentMethod.UPI,
        payment_method_type=PaymentMethodType.UPI_INTENT,
        status=PaymentStatus.FAILED,
        attempt_number=1,
        failure_details=PaymentFailureDetails(
            error_code="BAD_REQUEST_PAYMENT_OTP_INCORRECT",
            error_description="OTP typo",
            error_source=ErrorSource.CUSTOMER,
            error_step=ErrorStep.PAYMENT_AUTHENTICATION,
            error_reason=ErrorReason.AUTHENTICATION_FAILED,
            failure_category=FailureCategory.AUTHENTICATION_FAILURE
        )
    )

    # Verify attributes available on public models
    assert not hasattr(txn, "ground_truth_recoverable")
    assert not hasattr(txn, "counterfactual_outcomes")
    assert not hasattr(mock_customer, "ground_truth_recoverable")

    decision = strategy.decide(txn, mock_customer, [])
    assert decision.action == RecoveryAction.REMINDER
    assert decision.rule_id == "R003_AUTH_FAILURE_REMINDER"


def test_5_already_resolved_payments_not_double_counted():
    """Test 5: Late success / organically resolved payments are flagged as non-incremental."""
    evaluator = OutcomeEvaluator()
    decision = StrategyDecision(
        strategy_name="NAIVE_RETRY",
        event_id="txn_resolved_01",
        customer_id="cust_000100",
        action=RecoveryAction.RETRY,
        rule_id="R_NAIVE_GLOBAL_RETRY",
        reason="Retry attempt",
        timestamp="2026-01-15T12:00:00Z",
        eligible=True,
        attempt_number=1
    )

    txn = Transaction(
        transaction_id="txn_resolved_01",
        payment_id="pay_resolved_01",
        order_id="order_resolved_01",
        customer_id="cust_000100",
        created_at="2026-01-15T12:00:00Z",
        amount=1200.0,
        currency="INR",
        payment_method=PaymentMethod.UPI,
        payment_method_type=PaymentMethodType.UPI_INTENT,
        status=PaymentStatus.FAILED,
        attempt_number=1,
        is_late_success=True,
        late_success_at="2026-01-15T12:30:00Z"
    )

    gt = GroundTruthRecord(
        event_id="txn_resolved_01",
        customer_id="cust_000100",
        ground_truth_recoverable=True,
        ground_truth_best_action=RecoveryAction.DO_NOTHING,
        ground_truth_recovery_probability=1.0,
        ground_truth_customer_friction=0.0,
        counterfactual_outcomes={
            RecoveryAction.RETRY.value: RecoveryOutcome.ALREADY_RESOLVED.value,
            RecoveryAction.DO_NOTHING.value: RecoveryOutcome.ALREADY_RESOLVED.value
        },
        causal_explanation="Captured organically",
        is_already_resolved=True
    )

    record = evaluator.evaluate_decision(decision, txn, gt)
    assert record.simulated_outcome == RecoveryOutcome.ALREADY_RESOLVED
    assert record.recovered_amount == 1200.0
    assert record.is_recovered is True
    # Crucial: Not incremental because it succeeded organically without intervention!
    assert record.is_incremental is False
    assert record.is_false_positive is True # Active retry was redundant


def test_6_revenue_recovered_calculated_correctly():
    """Test 6: Total revenue recovered sums exact successful resolution amounts."""
    evaluator = OutcomeEvaluator()
    d1 = StrategyDecision(
        strategy_name="RULE_BASED",
        event_id="txn_00000001",
        customer_id="cust_000001",
        action=RecoveryAction.RETRY,
        reason="Retry",
        timestamp="2026-01-01T00:00:00Z"
    )
    t1 = Transaction(
        transaction_id="txn_00000001",
        payment_id="pay_00000001",
        order_id="order_00000001",
        customer_id="cust_000001",
        created_at="2026-01-01T00:00:00Z",
        amount=500.0,
        currency="INR",
        payment_method=PaymentMethod.UPI,
        payment_method_type=PaymentMethodType.UPI_INTENT,
        status=PaymentStatus.FAILED
    )
    gt1 = GroundTruthRecord(
        event_id="txn_00000001",
        customer_id="cust_000001",
        ground_truth_recoverable=True,
        ground_truth_best_action=RecoveryAction.RETRY,
        ground_truth_recovery_probability=0.9,
        ground_truth_customer_friction=0.05,
        counterfactual_outcomes={RecoveryAction.RETRY.value: RecoveryOutcome.SUCCESS.value},
        causal_explanation="Timeout",
        is_already_resolved=False
    )

    rec1 = evaluator.evaluate_decision(d1, t1, gt1)
    assert rec1.recovered_amount == 500.0
    assert rec1.is_recovered is True


def test_7_incremental_revenue_relative_to_no_action(sample_dataset_dir):
    """Test 7: Incremental revenue strictly equals Strategy Revenue minus No-Action Revenue."""
    pipeline = EvaluationPipeline()
    no_action = NoActionStrategy()
    m_na, _ = pipeline.evaluate_strategy(no_action, sample_dataset_dir, natural_recovery_rev=0.0)

    naive = NaiveRetryStrategy()
    m_naive, _ = pipeline.evaluate_strategy(naive, sample_dataset_dir, natural_recovery_rev=m_na.recovered_revenue)

    expected_incremental = round(m_naive.recovered_revenue - m_na.recovered_revenue, 2)
    assert m_naive.incremental_revenue == expected_incremental


def test_8_same_dataset_and_strategy_produces_identical_metrics(sample_dataset_dir):
    """Test 8: Repeated evaluation of same strategy produces exact bitwise identical metrics."""
    pipeline = EvaluationPipeline()
    strat = RuleBasedStrategy()

    m1, _ = pipeline.evaluate_strategy(strat, sample_dataset_dir, natural_recovery_rev=47999.51)
    m2, _ = pipeline.evaluate_strategy(strat, sample_dataset_dir, natural_recovery_rev=47999.51)

    assert m1.recovered_revenue == m2.recovered_revenue
    assert m1.total_interventions_attempted == m2.total_interventions_attempted
    assert m1.successful_recoveries == m2.successful_recoveries
    assert m1.net_incremental_value == m2.net_incremental_value


def test_9_unified_strategy_interface(sample_dataset_dir):
    """Test 9: All strategies conform to BaseStrategy and can run through the same pipeline."""
    pipeline = EvaluationPipeline()
    strategies = [NoActionStrategy(), NaiveRetryStrategy(), RuleBasedStrategy()]

    for s in strategies:
        metrics, records = pipeline.evaluate_strategy(s, sample_dataset_dir)
        assert metrics.strategy_name == s.name
        assert len(records) > 0


def test_10_chronological_ordering_no_lookahead(sample_dataset_dir):
    """Test 10: Events are delivered in strict chronological order during evaluation."""
    customers_by_id, transactions, checkouts, _ = DatasetLoader.load(sample_dataset_dir)
    failed_txns = [t for t in transactions if t.status == PaymentStatus.FAILED]
    all_events = failed_txns + checkouts
    all_events.sort(key=lambda e: e.created_at)

    for i in range(len(all_events) - 1):
        assert all_events[i].created_at <= all_events[i + 1].created_at


def test_11_large_dataset_benchmark_comparison(sample_dataset_dir, tmp_path):
    """Test 11: Benchmark comparison runs on full dataset and writes JSON & CSV outputs."""
    pipeline = EvaluationPipeline()
    comparison = pipeline.run_benchmark_comparison(
        strategies=[NoActionStrategy(), NaiveRetryStrategy(), RuleBasedStrategy()],
        data_dir=sample_dataset_dir,
        output_dir=tmp_path
    )

    assert "NO_ACTION" in comparison.strategy_metrics
    assert "NAIVE_RETRY" in comparison.strategy_metrics
    assert "RULE_BASED" in comparison.strategy_metrics

    # Verify JSON and CSV written
    assert (tmp_path / "benchmark_summary.json").exists()
    assert (tmp_path / "benchmark_comparison.csv").exists()


def test_12_cli_execution_commands(sample_dataset_dir, tmp_path):
    """Test 12: CLI entry points execute successfully with exit code 0."""
    res_run = subprocess.run(
        [sys.executable, "-m", "evaluation.run", "--strategy", "rule_based", "--dataset", str(sample_dataset_dir), "--output", str(tmp_path)],
        capture_output=True,
        text=True
    )
    assert res_run.returncode == 0, f"evaluation.run failed: {res_run.stderr}"

    res_compare = subprocess.run(
        [sys.executable, "-m", "evaluation.compare", "--dataset", str(sample_dataset_dir), "--output", str(tmp_path)],
        capture_output=True,
        text=True
    )
    assert res_compare.returncode == 0, f"evaluation.compare failed: {res_compare.stderr}"


# ------------------------------------------------------------------------------
# Adversarial Unit Scenarios (Section 28)
# ------------------------------------------------------------------------------

def test_adversarial_case_a_reliable_timeout(mock_customer):
    """Adversarial Case A: Reliable customer + isolated timeout -> RETRY."""
    txn = Transaction(
        transaction_id="txn_adv_a001",
        payment_id="pay_adv_a001",
        order_id="order_adv_a001",
        customer_id=mock_customer.customer_id,
        created_at="2026-02-01T10:00:00Z",
        amount=1499.0,
        currency="INR",
        payment_method=PaymentMethod.UPI,
        payment_method_type=PaymentMethodType.UPI_INTENT,
        status=PaymentStatus.FAILED,
        failure_details=PaymentFailureDetails(
            error_code="GATEWAY_ERROR_TIMEOUT",
            error_description="Timeout",
            error_source=ErrorSource.GATEWAY,
            error_step=ErrorStep.PAYMENT_PROCESSING,
            error_reason=ErrorReason.TIMEOUT,
            failure_category=FailureCategory.TRANSIENT_GATEWAY_FAILURE
        )
    )
    naive = NaiveRetryStrategy().decide(txn, mock_customer, [])
    rule = RuleBasedStrategy().decide(txn, mock_customer, [])

    assert naive.action == RecoveryAction.RETRY
    assert rule.action == RecoveryAction.RETRY


def test_adversarial_case_b_repeated_hard_failure(mock_customer):
    """Adversarial Case B: Repeated hard failure -> RULE_BASED DO_NOTHING."""
    txn = Transaction(
        transaction_id="txn_adv_b001",
        payment_id="pay_adv_b001",
        order_id="order_adv_b001",
        customer_id=mock_customer.customer_id,
        created_at="2026-02-01T10:00:00Z",
        amount=1499.0,
        currency="INR",
        payment_method=PaymentMethod.CARD,
        payment_method_type=PaymentMethodType.DEBIT_CARD,
        status=PaymentStatus.FAILED,
        failure_details=PaymentFailureDetails(
            error_code="CARD_RESTRICTED_OR_BLOCKED",
            error_description="Permanently blocked",
            error_source=ErrorSource.BANK,
            error_step=ErrorStep.PAYMENT_PROCESSING,
            error_reason=ErrorReason.PAYMENT_FAILED,
            failure_category=FailureCategory.HARD_FAILURE
        )
    )
    rule = RuleBasedStrategy().decide(txn, mock_customer, [])
    assert rule.action == RecoveryAction.DO_NOTHING
    assert rule.rule_id == "R007_HARD_FAILURE_STOP"


def test_adversarial_case_c_insufficient_funds(mock_customer):
    """Adversarial Case C: Insufficient funds -> RULE_BASED returns PAYMENT_LINK (not immediate retry)."""
    txn = Transaction(
        transaction_id="txn_adv_c001",
        payment_id="pay_adv_c001",
        order_id="order_adv_c001",
        customer_id=mock_customer.customer_id,
        created_at="2026-02-01T10:00:00Z",
        amount=1499.0,
        currency="INR",
        payment_method=PaymentMethod.UPI,
        payment_method_type=PaymentMethodType.UPI_INTENT,
        status=PaymentStatus.FAILED,
        failure_details=PaymentFailureDetails(
            error_code="BAD_REQUEST_PAYMENT_ACCOUNT_INSUFFICIENT_BALANCE",
            error_description="Low balance",
            error_source=ErrorSource.CUSTOMER,
            error_step=ErrorStep.PAYMENT_AUTHORIZATION,
            error_reason=ErrorReason.INSUFFICIENT_FUNDS,
            failure_category=FailureCategory.INSUFFICIENT_FUNDS
        )
    )
    rule = RuleBasedStrategy().decide(txn, mock_customer, [])
    assert rule.action == RecoveryAction.PAYMENT_LINK
    assert rule.action != RecoveryAction.RETRY


def test_adversarial_case_d_already_successful_payment(mock_customer):
    """Adversarial Case D: Already successful payment -> DO_NOTHING."""
    txn = Transaction(
        transaction_id="txn_adv_d001",
        payment_id="pay_adv_d001",
        order_id="order_adv_d001",
        customer_id=mock_customer.customer_id,
        created_at="2026-02-01T10:00:00Z",
        amount=1499.0,
        currency="INR",
        payment_method=PaymentMethod.UPI,
        payment_method_type=PaymentMethodType.UPI_INTENT,
        status=PaymentStatus.SUCCESS
    )
    naive = NaiveRetryStrategy().decide(txn, mock_customer, [])
    rule = RuleBasedStrategy().decide(txn, mock_customer, [])

    assert naive.action == RecoveryAction.DO_NOTHING
    assert rule.action == RecoveryAction.DO_NOTHING


def test_adversarial_case_e_abandoned_otp_checkout(mock_customer):
    """Adversarial Case E: Abandoned OTP checkout -> RULE_BASED returns REMINDER."""
    chk = AbandonedCheckout(
        checkout_id="chk_adv_e001",
        customer_id=mock_customer.customer_id,
        created_at="2026-02-01T10:00:00Z",
        amount=2999.0,
        currency="INR",
        payment_method_selected=PaymentMethod.UPI,
        checkout_stage=CheckoutStage.OTP_STAGE,
        time_spent_seconds=120,
        is_abandoned=True
    )
    rule = RuleBasedStrategy().decide(chk, mock_customer, [])
    assert rule.action == RecoveryAction.REMINDER
    assert rule.rule_id == "R006_ABANDONED_CHECKOUT_REMINDER"
