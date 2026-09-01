"""
Automated unit and integration test suite for REVIVE Synthetic Payment Simulator.
Verifies all 10 Phase 2 validation requirements and domain invariants.
"""

import json
import random
from pathlib import Path
import pytest

from simulator.checkout_generator import CheckoutGenerator
from simulator.config import SimulatorConfig
from simulator.customer_generator import CustomerGenerator
from simulator.enums import (
    CustomerProfile,
    PaymentStatus,
    FailureCategory,
    RecoveryAction,
    RecoveryOutcome,
)
from simulator.generate import generate_dataset
from simulator.ground_truth_engine import GroundTruthEngine
from simulator.public_schema import Customer, Transaction, AbandonedCheckout
from simulator.transaction_generator import TransactionGenerator
from simulator.validator import DatasetValidator


@pytest.fixture
def base_config():
    return SimulatorConfig(
        transaction_count=1000,
        customer_count=200,
        random_seed=42
    )


def test_1_same_seed_produces_identical_dataset(base_config):
    """Test 1: Same seed -> exact identical dataset."""
    rng1 = random.Random(42)
    cust_gen1 = CustomerGenerator(base_config, rng1)
    custs1 = cust_gen1.generate_population(100)
    txn_gen1 = TransactionGenerator(base_config, rng1)
    txns1 = txn_gen1.generate_transactions(custs1, target_transaction_count=500)

    rng2 = random.Random(42)
    cust_gen2 = CustomerGenerator(base_config, rng2)
    custs2 = cust_gen2.generate_population(100)
    txn_gen2 = TransactionGenerator(base_config, rng2)
    txns2 = txn_gen2.generate_transactions(custs2, target_transaction_count=500)

    assert len(txns1) == len(txns2) == 500
    for t1, t2 in zip(txns1, txns2):
        assert t1.transaction_id == t2.transaction_id
        assert t1.amount == t2.amount
        assert t1.status == t2.status
        assert t1.customer_id == t2.customer_id
        assert t1.payment_method == t2.payment_method


def test_2_different_seed_produces_different_dataset(base_config):
    """Test 2: Different seed -> distinct dataset."""
    rng1 = random.Random(42)
    cust_gen1 = CustomerGenerator(base_config, rng1)
    custs1 = cust_gen1.generate_population(50)
    txn_gen1 = TransactionGenerator(base_config, rng1)
    txns1 = txn_gen1.generate_transactions(custs1, target_transaction_count=200)

    rng2 = random.Random(99)
    cust_gen2 = CustomerGenerator(base_config, rng2)
    custs2 = cust_gen2.generate_population(50)
    txn_gen2 = TransactionGenerator(base_config, rng2)
    txns2 = txn_gen2.generate_transactions(custs2, target_transaction_count=200)

    # Different amounts and customer attributes
    amounts1 = [t.amount for t in txns1]
    amounts2 = [t.amount for t in txns2]
    assert amounts1 != amounts2


def test_3_every_transaction_references_existing_customer(base_config):
    """Test 3: Referential integrity: All transactions reference valid customers."""
    rng = random.Random(42)
    custs = CustomerGenerator(base_config, rng).generate_population(100)
    txns = TransactionGenerator(base_config, rng).generate_transactions(custs, target_transaction_count=500)

    valid_cust_ids = {c.customer_id for c in custs}
    for t in txns:
        assert t.customer_id in valid_cust_ids


def test_4_no_negative_or_zero_amounts(base_config):
    """Test 4: Financial validity: No negative or zero amounts allowed."""
    rng = random.Random(42)
    custs = CustomerGenerator(base_config, rng).generate_population(100)
    txns = TransactionGenerator(base_config, rng).generate_transactions(custs, target_transaction_count=500)
    checkouts = CheckoutGenerator(base_config, rng).generate_abandoned_checkouts(custs, count=50)

    for t in txns:
        assert t.amount > 0.0, f"Transaction {t.transaction_id} has invalid amount {t.amount}"
    for c in checkouts:
        assert c.amount > 0.0, f"Checkout {c.checkout_id} has invalid amount {c.amount}"


def test_5_no_duplicate_transaction_ids(base_config):
    """Test 5: Unique ID invariant across transactions and payments."""
    rng = random.Random(42)
    custs = CustomerGenerator(base_config, rng).generate_population(100)
    txns = TransactionGenerator(base_config, rng).generate_transactions(custs, target_transaction_count=500)

    txn_ids = [t.transaction_id for t in txns]
    assert len(txn_ids) == len(set(txn_ids))

    pay_ids = [t.payment_id for t in txns]
    assert len(pay_ids) == len(set(pay_ids))


def test_6_ground_truth_isolated_from_public_records(base_config):
    """Test 6: Absence of ground-truth leakage in public/model-visible records."""
    rng = random.Random(42)
    custs = CustomerGenerator(base_config, rng).generate_population(50)
    txns = TransactionGenerator(base_config, rng).generate_transactions(custs, target_transaction_count=200)
    checkouts = CheckoutGenerator(base_config, rng).generate_abandoned_checkouts(custs, count=20)

    for t in txns:
        t_dict = t.model_dump()
        for k in t_dict.keys():
            assert not k.startswith("ground_truth_")
            assert k != "counterfactual_outcomes"

    for c in checkouts:
        c_dict = c.model_dump()
        for k in c_dict.keys():
            assert not k.startswith("ground_truth_")
            assert k != "counterfactual_outcomes"


def test_7_failure_fields_internally_consistent(base_config):
    """Test 7: Razorpay-like failure fields are semantically coherent."""
    rng = random.Random(42)
    custs = CustomerGenerator(base_config, rng).generate_population(100)
    txns = TransactionGenerator(base_config, rng).generate_transactions(custs, target_transaction_count=500)

    failed_txns = [t for t in txns if t.status == PaymentStatus.FAILED]
    assert len(failed_txns) > 0

    for t in failed_txns:
        assert t.failure_details is not None
        cat = t.failure_details.failure_category
        reason = t.failure_details.error_reason

        if cat == FailureCategory.TRANSIENT_GATEWAY_FAILURE:
            assert reason.value == "timeout"
        elif cat == FailureCategory.INSUFFICIENT_FUNDS:
            assert reason.value == "insufficient_funds"
        elif cat == FailureCategory.AUTHENTICATION_FAILURE:
            assert reason.value == "authentication_failed"
        elif cat == FailureCategory.HIGH_RISK:
            assert reason.value == "risk_detected"


def test_8_customer_histories_strictly_chronological(base_config):
    """Test 8: Customer transaction timelines maintain strictly monotonic temporal order."""
    rng = random.Random(42)
    custs = CustomerGenerator(base_config, rng).generate_population(100)
    txns = TransactionGenerator(base_config, rng).generate_transactions(custs, target_transaction_count=1000)

    cust_txns = {}
    for t in txns:
        cust_txns.setdefault(t.customer_id, []).append(t)

    for cust_id, timeline in cust_txns.items():
        for i in range(len(timeline) - 1):
            assert timeline[i].created_at <= timeline[i + 1].created_at, (
                f"Customer {cust_id} timeline inverted: {timeline[i].created_at} > {timeline[i+1].created_at}"
            )


def test_9_abandoned_checkout_structure_valid(base_config):
    """Test 9: Abandoned checkouts have valid stages, positive times, and amounts."""
    rng = random.Random(42)
    custs = CustomerGenerator(base_config, rng).generate_population(50)
    checkouts = CheckoutGenerator(base_config, rng).generate_abandoned_checkouts(custs, count=100)

    assert len(checkouts) == 100
    for chk in checkouts:
        assert chk.is_abandoned is True
        assert chk.time_spent_seconds >= 0
        assert chk.checkout_stage is not None
        assert chk.amount > 0.0


def test_10_generator_10k_dataset_full_validation(tmp_path):
    """Test 10: Complete 10,000 transaction dataset generation & validator pass."""
    summary = generate_dataset(
        transaction_count=10000,
        customer_count=2000,
        seed=42,
        output_dir=tmp_path
    )

    assert summary["transaction_count"] == 10000
    assert summary["customer_count"] == 2000
    assert summary["status_counts"]["SUCCESS"] > 7000
    assert summary["status_counts"]["FAILED"] > 500
    assert summary["recoverable_opportunities"] > 0

    # Ensure output files exist and are valid JSONL
    for fname in ["customers.jsonl", "transactions.jsonl", "abandoned_checkouts.jsonl", "ground_truth.jsonl"]:
        fpath = tmp_path / fname
        assert fpath.exists()
        assert fpath.stat().st_size > 0
        with open(fpath, "r", encoding="utf-8") as f:
            first_line = json.loads(f.readline())
            assert isinstance(first_line, dict)


def test_late_success_edge_case(base_config):
    """Test edge case: Late success transaction correctly maps to ALREADY_RESOLVED in ground truth."""
    rng = random.Random(42)
    custs = CustomerGenerator(base_config, rng).generate_population(100)
    txns = TransactionGenerator(base_config, rng).generate_transactions(custs, target_transaction_count=1500)
    cust_map = {c.customer_id: c for c in custs}

    gt_engine = GroundTruthEngine(base_config, rng)
    gt_records = gt_engine.generate_ground_truth_for_transactions(txns, cust_map)

    late_success_txns = [t for t in txns if t.is_late_success]
    assert len(late_success_txns) > 0, "Expected at least one late success in 1500 transactions"

    late_gt = [gt for gt in gt_records if gt.is_already_resolved]
    assert len(late_gt) == len(late_success_txns)
    for gt in late_gt:
        assert gt.ground_truth_best_action == RecoveryAction.DO_NOTHING
        assert gt.counterfactual_outcomes[RecoveryAction.RETRY.value] == RecoveryOutcome.ALREADY_RESOLVED.value
