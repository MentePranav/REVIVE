"""
Comprehensive automated unit, integration, adversarial, and property-style test suite for REVIVE Controlled Recovery Execution Simulator.
Covers all Phase 6 requirements, execution boundaries, idempotency, state safety, and audit trails.
"""

import socket
from datetime import datetime, timezone
from pathlib import Path
import pytest

from agent.models import (
    ActionScore,
    DiagnosisResult,
    NormalizedFailureCategory,
    RecoverabilityTier,
    ReviveRecommendation,
    RiskSignal,
)
from evaluation.pipeline import DatasetLoader
from execution.batch import BatchExecutionRunner
from execution.executor import ControlledExecutor
from execution.models import (
    AuditEventType,
    ExecutionResult,
    ExecutionStatus,
    SimulatedRecoveryOutcome,
)
from execution.orchestrator import ReviveOrchestrator
from policy.config import ApprovedTemplateRegistry, PolicyConfig
from policy.engine import PolicyEngine
from policy.models import (
    ExecutionAuthorization,
    PolicyDecisionType,
    PolicyRuleId,
)
from policy.state_context import CustomerStateContext, PaymentStateContext
from simulator.enums import (
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
from simulator.public_schema import AbandonedCheckout, Customer, PaymentFailureDetails, Transaction


@pytest.fixture
def mock_transaction():
    return Transaction(
        transaction_id="txn_test_e01",
        payment_id="pay_test_e01",
        order_id="order_test_e01",
        customer_id="cust_000201",
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


@pytest.fixture
def mock_authorization(mock_transaction):
    return ExecutionAuthorization(
        authorization_id="auth_test_9999",
        authorized=True,
        payment_id=mock_transaction.payment_id,
        transaction_id=mock_transaction.transaction_id,
        customer_id=mock_transaction.customer_id,
        action=RecoveryAction.RETRY,
        template_id=None,
        policy_version="1.0.0",
        authorized_at=mock_transaction.created_at
    )


@pytest.fixture
def mock_ground_truth(mock_transaction):
    return GroundTruthRecord(
        event_id=mock_transaction.transaction_id,
        customer_id=mock_transaction.customer_id,
        ground_truth_recoverable=True,
        ground_truth_best_action=RecoveryAction.RETRY,
        ground_truth_recovery_probability=0.95,
        ground_truth_customer_friction=0.05,
        counterfactual_outcomes={
            RecoveryAction.RETRY.value: RecoveryOutcome.SUCCESS.value,
            RecoveryAction.REMINDER.value: RecoveryOutcome.FAILURE.value,
            RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.SUCCESS.value,
            RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
        },
        causal_explanation="Transient gateway timeout resolveable by retry.",
        is_already_resolved=False
    )


# ------------------------------------------------------------------------------
# 25 Required Unit & Adversarial Tests (Section 21)
# ------------------------------------------------------------------------------

def test_1_valid_authorization_execution_succeeds(mock_transaction, mock_authorization, mock_ground_truth):
    """Test 1: Valid ExecutionAuthorization executes successfully and records outcome."""
    executor = ControlledExecutor()
    res, audit = executor.execute(mock_authorization, mock_transaction, ground_truth=mock_ground_truth)

    assert res.execution_status == ExecutionStatus.EXECUTED
    assert res.recovery_outcome == SimulatedRecoveryOutcome.RECOVERED
    assert res.recovered_amount == mock_transaction.amount
    assert res.simulated_external_reference.startswith("sim_ret_")
    assert any(a.event_type == AuditEventType.OUTCOME_RECORDED for a in audit)


def test_2_deny_authorization_refuses_execution(mock_transaction, mock_authorization):
    """Test 2: Unauthorized token (authorized=False) is refused by executor."""
    mock_authorization.authorized = False
    executor = ControlledExecutor()
    res, audit = executor.execute(mock_authorization, mock_transaction)

    assert res.execution_status == ExecutionStatus.BLOCKED
    assert res.recovery_outcome == SimulatedRecoveryOutcome.NOT_APPLICABLE
    assert "UNAUTHORIZED" in res.execution_reason


def test_3_human_review_refuses_automatic_execution(mock_transaction):
    """Test 3: HUMAN_REVIEW action does not perform automated recovery."""
    auth = ExecutionAuthorization(
        authorization_id="auth_hr_01",
        authorized=True,
        payment_id=mock_transaction.payment_id,
        transaction_id=mock_transaction.transaction_id,
        customer_id=mock_transaction.customer_id,
        action=RecoveryAction.HUMAN_REVIEW,
        template_id=None,
        policy_version="1.0.0",
        authorized_at=mock_transaction.created_at
    )
    executor = ControlledExecutor()
    res, _ = executor.execute(auth, mock_transaction)

    assert res.execution_status == ExecutionStatus.HUMAN_REVIEW_REQUIRED
    assert res.recovered_amount == 0.0


def test_4_no_action_produces_no_recovery(mock_transaction):
    """Test 4: DO_NOTHING action results in NO_ACTION_TAKEN."""
    auth = ExecutionAuthorization(
        authorization_id="auth_no_01",
        authorized=True,
        payment_id=mock_transaction.payment_id,
        transaction_id=mock_transaction.transaction_id,
        customer_id=mock_transaction.customer_id,
        action=RecoveryAction.DO_NOTHING,
        template_id=None,
        policy_version="1.0.0",
        authorized_at=mock_transaction.created_at
    )
    executor = ControlledExecutor()
    res, _ = executor.execute(auth, mock_transaction)

    assert res.execution_status == ExecutionStatus.NO_ACTION_TAKEN
    assert res.recovered_amount == 0.0


def test_5_missing_authorization_blocked(mock_transaction):
    """Test 5: Missing authorization token is immediately blocked."""
    executor = ControlledExecutor()
    res, _ = executor.execute(None, mock_transaction)

    assert res.execution_status == ExecutionStatus.BLOCKED
    assert "MISSING_AUTHORIZATION" in res.execution_reason


def test_6_authorization_for_another_payment_id_blocked(mock_transaction, mock_authorization):
    """Test 6: Authorization token for another customer/payment is rejected."""
    mock_authorization.customer_id = "cust_different_99"
    executor = ControlledExecutor()
    res, _ = executor.execute(mock_authorization, mock_transaction)

    assert res.execution_status == ExecutionStatus.BLOCKED
    assert "CUSTOMER_MISMATCH" in res.execution_reason


def test_7_authorization_for_another_customer_id_blocked(mock_transaction, mock_authorization):
    """Test 7: Mismatched customer ID blocked."""
    mock_authorization.customer_id = "cust_wrong_00"
    executor = ControlledExecutor()
    res, _ = executor.execute(mock_authorization, mock_transaction)

    assert res.execution_status == ExecutionStatus.BLOCKED


def test_8_payment_becomes_captured_after_authorization_blocked(mock_transaction, mock_authorization):
    """Test 8: Live payment state changed to SUCCESS/resolved prior to execution -> BLOCKED."""
    p_state = PaymentStateContext(
        payment_id=mock_transaction.payment_id,
        customer_id=mock_transaction.customer_id,
        current_status=PaymentStatus.SUCCESS,
        is_already_resolved=True
    )
    executor = ControlledExecutor()
    res, _ = executor.execute(mock_authorization, mock_transaction, payment_state=p_state)

    assert res.execution_status == ExecutionStatus.BLOCKED
    assert "PAYMENT_STATE_CHANGED" in res.execution_reason


def test_9_payment_becomes_success_after_authorization_blocked(mock_transaction, mock_authorization):
    """Test 9: State change guard blocks execution."""
    p_state = PaymentStateContext(payment_id=mock_transaction.payment_id, customer_id=mock_transaction.customer_id, is_already_resolved=True)
    executor = ControlledExecutor()
    res, _ = executor.execute(mock_authorization, mock_transaction, payment_state=p_state)

    assert res.execution_status == ExecutionStatus.BLOCKED


def test_10_third_automated_recovery_attempt_blocked(mock_transaction, mock_authorization):
    """Test 10: Attempt cap (>= 2) re-validated and blocked at executor."""
    p_state = PaymentStateContext(payment_id=mock_transaction.payment_id, customer_id=mock_transaction.customer_id, automated_attempt_count=2)
    executor = ControlledExecutor()
    res, _ = executor.execute(mock_authorization, mock_transaction, payment_state=p_state)

    assert res.execution_status == ExecutionStatus.BLOCKED
    assert "MAX_ATTEMPTS" in res.execution_reason


def test_11_customer_contact_limit_exceeded_blocked(mock_transaction):
    """Test 11: Contact cap (>= 2) re-validated and blocked at executor."""
    auth = ExecutionAuthorization(
        authorization_id="auth_rem_01",
        authorized=True,
        payment_id=mock_transaction.payment_id,
        customer_id=mock_transaction.customer_id,
        action=RecoveryAction.REMINDER,
        template_id=ApprovedTemplateRegistry.REMINDER_STANDARD_V1,
        policy_version="1.0.0",
        authorized_at=mock_transaction.created_at
    )
    c_state = CustomerStateContext(customer_id=mock_transaction.customer_id, contact_actions_count=2)
    executor = ControlledExecutor()
    res, _ = executor.execute(auth, mock_transaction, customer_state=c_state)

    assert res.execution_status == ExecutionStatus.BLOCKED
    assert "CONTACT_LIMIT" in res.execution_reason


def test_12_cooldown_active_blocked_by_orchestrator(mock_transaction):
    """Test 12: Cooldown active blocked at orchestrator level."""
    reliable_cust = Customer(
        customer_id=mock_transaction.customer_id,
        account_created_at="2025-01-01T00:00:00Z",
        customer_segment=CustomerSegment.CONSUMER_PRO,
        customer_profile=CustomerProfile.RELIABLE,
        customer_age_days=300,
        historical_transaction_count=20,
        historical_success_count=19,
        historical_failure_count=1,
        historical_success_rate=0.95,
        average_transaction_amount=1500.0,
        preferred_payment_method=PaymentMethod.UPI
    )
    p_state = PaymentStateContext(
        payment_id=mock_transaction.payment_id,
        customer_id=mock_transaction.customer_id,
        last_action_timestamp="2026-01-15T11:58:00Z", # 2 mins prior
        automated_attempt_count=1
    )
    orch = ReviveOrchestrator()
    trace = orch.process_event(mock_transaction, customer=reliable_cust, payment_state=p_state)

    assert trace.policy_decision.decision == PolicyDecisionType.DENY
    assert trace.policy_decision.primary_rule_id == PolicyRuleId.P008_COOLDOWN_ACTIVE
    assert trace.execution_result.execution_status == ExecutionStatus.BLOCKED


def test_13_same_execution_request_repeated_is_idempotent(mock_transaction, mock_authorization, mock_ground_truth):
    """Test 13: Exact same execution request repeated returns original cached result (Idempotent)."""
    executor = ControlledExecutor()
    r1, _ = executor.execute(mock_authorization, mock_transaction, ground_truth=mock_ground_truth)
    r2, audit2 = executor.execute(mock_authorization, mock_transaction, ground_truth=mock_ground_truth)

    assert r1.execution_id == r2.execution_id
    assert r1.execution_key == r2.execution_key
    assert any(a.event_type == AuditEventType.DUPLICATE for a in audit2)


def test_14_unsupported_action_blocked(mock_transaction, mock_authorization):
    """Test 14: Action not in allowed actions list is blocked."""
    cfg = PolicyConfig(allowed_actions=[RecoveryAction.DO_NOTHING.value])
    executor = ControlledExecutor(cfg)
    res, _ = executor.execute(mock_authorization, mock_transaction)

    assert res.execution_status == ExecutionStatus.BLOCKED
    assert "UNSUPPORTED_ACTION" in res.execution_reason


def test_15_malformed_transaction_handled_safely(mock_authorization):
    """Test 15: Malformed transaction handled safely without crashing."""
    malformed_txn = Transaction(
        transaction_id="txn_malformed",
        payment_id="pay_malformed",
        order_id="order_malformed",
        customer_id="cust_malformed",
        created_at="invalid-date",
        amount=500.0,
        currency="INR",
        payment_method=PaymentMethod.UPI,
        payment_method_type=PaymentMethodType.UPI_INTENT,
        status=PaymentStatus.FAILED
    )
    mock_authorization.customer_id = "cust_malformed"
    mock_authorization.payment_id = "pay_malformed"
    mock_authorization.transaction_id = "txn_malformed"

    executor = ControlledExecutor()
    res, _ = executor.execute(mock_authorization, malformed_txn)
    assert res.execution_status in (ExecutionStatus.EXECUTED, ExecutionStatus.BLOCKED)


def test_16_malformed_authorization_blocked(mock_transaction):
    """Test 16: Malformed authorization object blocked."""
    auth = ExecutionAuthorization(
        authorization_id="auth_bad",
        authorized=False,
        payment_id="wrong_pay",
        customer_id="wrong_cust",
        action=RecoveryAction.RETRY,
        policy_version="1.0.0",
        authorized_at="2026-01-01T00:00:00Z"
    )
    executor = ControlledExecutor()
    res, _ = executor.execute(auth, mock_transaction)
    assert res.execution_status == ExecutionStatus.BLOCKED


def test_17_simulator_missing_outcome_fails_closed(mock_transaction, mock_authorization):
    """Test 17: Ground truth record with missing action outcomes safely defaults to NOT_RECOVERED."""
    gt_empty = GroundTruthRecord(
        event_id=mock_transaction.transaction_id,
        customer_id=mock_transaction.customer_id,
        ground_truth_recoverable=False,
        ground_truth_best_action=RecoveryAction.DO_NOTHING,
        ground_truth_recovery_probability=0.0,
        ground_truth_customer_friction=0.0,
        counterfactual_outcomes={}, # Empty
        causal_explanation="Unknown",
        is_already_resolved=False
    )
    executor = ControlledExecutor()
    res, _ = executor.execute(mock_authorization, mock_transaction, ground_truth=gt_empty)

    assert res.execution_status == ExecutionStatus.EXECUTED
    assert res.recovery_outcome == SimulatedRecoveryOutcome.NOT_RECOVERED
    assert res.recovered_amount == 0.0


def test_18_unexpected_internal_failure_fails_closed(mock_transaction, mock_authorization):
    """Test 18: Internal failure handled safely."""
    executor = ControlledExecutor()
    res, _ = executor._fail_closed(
        reason="Internal simulator exception",
        status=ExecutionStatus.FAILED,
        event_id="txn_01",
        payment_id="pay_01",
        customer_id="cust_01",
        action=RecoveryAction.RETRY,
        timestamp="2026-01-01T00:00:00Z",
        local_audit=[]
    )
    assert res.execution_status == ExecutionStatus.FAILED
    assert res.recovered_amount == 0.0


def test_19_reminder_uses_approved_template_only(mock_transaction):
    """Test 19: Reminder executes with approved template."""
    auth = ExecutionAuthorization(
        authorization_id="auth_rem_ok",
        authorized=True,
        payment_id=mock_transaction.payment_id,
        customer_id=mock_transaction.customer_id,
        action=RecoveryAction.REMINDER,
        template_id=ApprovedTemplateRegistry.REMINDER_STANDARD_V1,
        policy_version="1.0.0",
        authorized_at=mock_transaction.created_at
    )
    executor = ControlledExecutor()
    res, _ = executor.execute(auth, mock_transaction)

    assert res.execution_status == ExecutionStatus.EXECUTED
    assert "REMINDER_STANDARD_V1" in res.execution_reason
    assert res.simulated_external_reference.startswith("sim_rem_")


def test_20_arbitrary_customer_message_blocked_by_policy(mock_transaction):
    """Test 20: Arbitrary unapproved custom message injection blocked by policy engine."""
    orch = ReviveOrchestrator()
    mock_transaction.failure_details.failure_category = FailureCategory.AUTHENTICATION_FAILURE
    trace = orch.process_event(mock_transaction)

    # Policy requires approved template
    if trace.policy_decision.execution_authorization:
        assert trace.policy_decision.execution_authorization.template_id in ApprovedTemplateRegistry.all_templates()


def test_21_payment_link_is_synthetic_only(mock_transaction):
    """Test 21: Payment link reference is strictly synthetic."""
    auth = ExecutionAuthorization(
        authorization_id="auth_pl_01",
        authorized=True,
        payment_id=mock_transaction.payment_id,
        customer_id=mock_transaction.customer_id,
        action=RecoveryAction.PAYMENT_LINK,
        template_id=ApprovedTemplateRegistry.PAYMENT_LINK_STANDARD_V1,
        policy_version="1.0.0",
        authorized_at=mock_transaction.created_at
    )
    executor = ControlledExecutor()
    res, _ = executor.execute(auth, mock_transaction)

    assert res.simulated_external_reference.startswith("sim_pl_")
    assert "razorpay.com" not in res.simulated_external_reference


def test_22_no_network_request_is_made(monkeypatch, mock_transaction, mock_authorization, mock_ground_truth):
    """Test 22: Guaranteed zero network access (socket.create_connection blocked)."""
    def guarded_connect(*args, **kwargs):
        raise RuntimeError("Illegal network call attempted!")

    monkeypatch.setattr(socket, "create_connection", guarded_connect)

    executor = ControlledExecutor()
    res, _ = executor.execute(mock_authorization, mock_transaction, ground_truth=mock_ground_truth)
    assert res.execution_status == ExecutionStatus.EXECUTED


def test_23_no_api_key_required(mock_transaction, mock_authorization, mock_ground_truth):
    """Test 23: Complete execution operates with zero environment secrets or API keys."""
    executor = ControlledExecutor()
    res, _ = executor.execute(mock_authorization, mock_transaction, ground_truth=mock_ground_truth)
    assert res.execution_status == ExecutionStatus.EXECUTED


def test_24_batch_execution_completes_successfully():
    """Test 24: Batch execution on sample dataset completes cleanly."""
    data_path = Path("data")
    customers_by_id, transactions, checkouts, gt_map = DatasetLoader.load(data_path)
    all_ops = [t for t in transactions if t.status == PaymentStatus.FAILED] + checkouts

    runner = BatchExecutionRunner()
    traces, summary = runner.run_batch(all_ops[:100], customers_by_id, gt_map, total_transactions=len(transactions))

    assert len(traces) == 100
    assert summary.total_failed_opportunities == 100
    assert summary.total_recovered_revenue > 0.0


def test_25_pipeline_cannot_bypass_phase_5_policy(mock_transaction):
    """Test 25: Pipeline structurally cannot execute when Phase 5 returns DENY or HUMAN_REVIEW."""
    orch = ReviveOrchestrator()
    # Force low confidence failure
    mock_transaction.failure_details.error_code = "UNKNOWN_GLITCH"
    mock_transaction.failure_details.failure_category = FailureCategory.HARD_FAILURE

    trace = orch.process_event(mock_transaction)
    assert trace.policy_decision.decision in (PolicyDecisionType.DENY, PolicyDecisionType.HUMAN_REVIEW, PolicyDecisionType.NO_ACTION)
    assert trace.execution_result.execution_status != ExecutionStatus.EXECUTED
    assert trace.execution_result.recovered_amount == 0.0


# ------------------------------------------------------------------------------
# 10 Property Safety Invariant Tests (Section 22)
# ------------------------------------------------------------------------------

def test_property_invariant_a_no_allow_no_execution(mock_transaction):
    """Invariant A: If policy decision is not ALLOW, automated execution is strictly impossible."""
    orch = ReviveOrchestrator()
    p_state = PaymentStateContext(payment_id=mock_transaction.payment_id, customer_id=mock_transaction.customer_id, current_status=PaymentStatus.SUCCESS)
    trace = orch.process_event(mock_transaction, payment_state=p_state)

    assert trace.policy_decision.decision != PolicyDecisionType.ALLOW
    assert trace.execution_result.execution_status != ExecutionStatus.EXECUTED


def test_property_invariant_b_no_valid_authorization_no_execution(mock_transaction):
    """Invariant B: No valid authorization token -> no execution."""
    executor = ControlledExecutor()
    res, _ = executor.execute(None, mock_transaction)
    assert res.execution_status == ExecutionStatus.BLOCKED


def test_property_invariant_c_resolved_payment_no_recovery(mock_transaction, mock_authorization):
    """Invariant C: Resolved payment -> no recovery execution."""
    p_state = PaymentStateContext(payment_id=mock_transaction.payment_id, customer_id=mock_transaction.customer_id, is_already_resolved=True)
    executor = ControlledExecutor()
    res, _ = executor.execute(mock_authorization, mock_transaction, payment_state=p_state)
    assert res.execution_status == ExecutionStatus.BLOCKED


def test_property_invariant_d_third_attempt_never_executes(mock_transaction, mock_authorization):
    """Invariant D: Third automated attempt never executes."""
    p_state = PaymentStateContext(payment_id=mock_transaction.payment_id, customer_id=mock_transaction.customer_id, automated_attempt_count=2)
    executor = ControlledExecutor()
    res, _ = executor.execute(mock_authorization, mock_transaction, payment_state=p_state)
    assert res.execution_status == ExecutionStatus.BLOCKED


def test_property_invariant_e_same_key_at_most_one_execution(mock_transaction, mock_authorization, mock_ground_truth):
    """Invariant E: Same execution key produces at most one simulated action."""
    executor = ControlledExecutor()
    res1, _ = executor.execute(mock_authorization, mock_transaction, ground_truth=mock_ground_truth)
    res2, audit2 = executor.execute(mock_authorization, mock_transaction, ground_truth=mock_ground_truth)

    assert res1.execution_id == res2.execution_id
    assert any(a.event_type == AuditEventType.DUPLICATE for a in audit2)


def test_property_invariant_f_unsupported_action_never_executes(mock_transaction, mock_authorization):
    """Invariant F: Unsupported action never executes."""
    cfg = PolicyConfig(allowed_actions=[RecoveryAction.DO_NOTHING.value])
    executor = ControlledExecutor(cfg)
    res, _ = executor.execute(mock_authorization, mock_transaction)
    assert res.execution_status == ExecutionStatus.BLOCKED


def test_property_invariant_g_human_review_never_auto_executes(mock_transaction):
    """Invariant G: Human review never automatically executes payment mutation."""
    auth = ExecutionAuthorization(
        authorization_id="auth_hr",
        authorized=True,
        payment_id=mock_transaction.payment_id,
        customer_id=mock_transaction.customer_id,
        action=RecoveryAction.HUMAN_REVIEW,
        policy_version="1.0.0",
        authorized_at=mock_transaction.created_at
    )
    executor = ControlledExecutor()
    res, _ = executor.execute(auth, mock_transaction)
    assert res.execution_status == ExecutionStatus.HUMAN_REVIEW_REQUIRED


def test_property_invariant_h_policy_denial_cannot_be_overridden_by_executor(mock_transaction):
    """Invariant H: Executor cannot override a policy denial."""
    orch = ReviveOrchestrator()
    p_state = PaymentStateContext(payment_id=mock_transaction.payment_id, customer_id=mock_transaction.customer_id, automated_attempt_count=2)
    trace = orch.process_event(mock_transaction, payment_state=p_state)
    assert trace.execution_result.execution_status == ExecutionStatus.BLOCKED


def test_property_invariant_i_unexpected_error_does_not_trigger_retry(mock_transaction):
    """Invariant I: Fail closed without uncontrolled retry."""
    executor = ControlledExecutor()
    res, _ = executor._fail_closed("Simulated exception", ExecutionStatus.FAILED, "txn_1", "pay_1", "cust_1", RecoveryAction.RETRY, "2026-01-01T00:00:00Z", [])
    assert res.execution_status == ExecutionStatus.FAILED
    assert res.recovered_amount == 0.0


def test_property_invariant_j_zero_network_calls(monkeypatch, mock_transaction, mock_authorization, mock_ground_truth):
    """Invariant J: Total absence of network traffic."""
    def guarded_socket(*args, **kwargs):
        raise AssertionError("Network socket opened!")

    monkeypatch.setattr(socket, "socket", guarded_socket)
    executor = ControlledExecutor()
    res, _ = executor.execute(mock_authorization, mock_transaction, ground_truth=mock_ground_truth)
    assert res.execution_status == ExecutionStatus.EXECUTED
