"""
Comprehensive validator engine for synthetic payment datasets.
Enforces structural integrity, referential consistency, chronological sanity, and zero ground-truth leakage.
"""

from datetime import datetime
from typing import List, Dict, Set, Tuple

from simulator.enums import (
    CustomerProfile,
    PaymentMethod,
    PaymentStatus,
    FailureCategory,
    ErrorSource,
    ErrorStep,
    ErrorReason,
    CheckoutStage,
)
from simulator.ground_truth_schema import GroundTruthRecord
from simulator.public_schema import AbandonedCheckout, Customer, Transaction


class ValidationResult:
    """Encapsulates validation status and diagnostic issue log."""

    def __init__(self):
        self.is_valid: bool = True
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def add_error(self, message: str):
        self.is_valid = False
        self.errors.append(message)

    def add_warning(self, message: str):
        self.warnings.append(message)


class DatasetValidator:
    """Validates full synthetic payment collections."""

    @classmethod
    def validate(
        cls,
        customers: List[Customer],
        transactions: List[Transaction],
        checkouts: List[AbandonedCheckout],
        ground_truth_records: List[GroundTruthRecord]
    ) -> ValidationResult:
        res = ValidationResult()

        customer_ids: Set[str] = set()
        customers_by_id: Dict[str, Customer] = {}

        # 1. Validate Customers
        for c in customers:
            if c.customer_id in customer_ids:
                res.add_error(f"Duplicate customer ID detected: {c.customer_id}")
            customer_ids.add(c.customer_id)
            customers_by_id[c.customer_id] = c

            # Check historical count consistency
            if c.historical_transaction_count != (c.historical_success_count + c.historical_failure_count):
                res.add_error(
                    f"Customer {c.customer_id} history count mismatch: total={c.historical_transaction_count}, "
                    f"success={c.historical_success_count}, failure={c.historical_failure_count}"
                )

            # Check success rate calculation
            if c.historical_transaction_count > 0:
                expected_rate = round(c.historical_success_count / c.historical_transaction_count, 4)
                if abs(c.historical_success_rate - expected_rate) > 0.01:
                    res.add_error(
                        f"Customer {c.customer_id} success rate mismatch: reported={c.historical_success_rate}, expected={expected_rate}"
                    )

            if c.average_transaction_amount <= 0.0 and c.historical_transaction_count > 0:
                res.add_error(f"Customer {c.customer_id} has invalid non-positive average transaction amount")

        # 2. Validate Transactions
        txn_ids: Set[str] = set()
        pay_ids: Set[str] = set()
        cust_txns_map: Dict[str, List[Transaction]] = {}

        for t in transactions:
            # Duplicate ID check
            if t.transaction_id in txn_ids:
                res.add_error(f"Duplicate transaction ID: {t.transaction_id}")
            txn_ids.add(t.transaction_id)

            if t.payment_id in pay_ids:
                res.add_error(f"Duplicate payment ID: {t.payment_id}")
            pay_ids.add(t.payment_id)

            # Referential integrity
            if t.customer_id not in customer_ids:
                res.add_error(f"Transaction {t.transaction_id} references non-existent customer: {t.customer_id}")

            # Financial validity
            if t.amount <= 0.0:
                res.add_error(f"Transaction {t.transaction_id} has non-positive amount: {t.amount}")

            # Status and Failure Details consistency
            if t.status == PaymentStatus.FAILED:
                if t.failure_details is None:
                    res.add_error(f"Failed transaction {t.transaction_id} is missing failure_details")
                else:
                    cls._validate_failure_semantics(t, res)
            elif t.status == PaymentStatus.SUCCESS:
                if t.failure_details is not None:
                    res.add_error(f"Successful transaction {t.transaction_id} should not have failure_details")

            # Leakage Check: Ensure public transaction has no ground truth attributes
            t_dict = t.model_dump()
            for key in t_dict:
                if key.startswith("ground_truth_") or key == "counterfactual_outcomes":
                    res.add_error(f"CRITICAL GROUND TRUTH LEAKAGE in transaction {t.transaction_id}: field {key}")

            cust_txns_map.setdefault(t.customer_id, []).append(t)

        # 3. Validate Customer Timelines (Strict Chronological Order)
        for cust_id, txn_list in cust_txns_map.items():
            prev_dt: datetime | None = None
            for txn in txn_list:
                try:
                    dt = datetime.fromisoformat(txn.created_at.replace("Z", "+00:00"))
                except ValueError:
                    res.add_error(f"Invalid timestamp format in transaction {txn.transaction_id}: {txn.created_at}")
                    continue

                if prev_dt is not None and dt < prev_dt:
                    res.add_error(
                        f"Chronological order violation for customer {cust_id}: txn {txn.transaction_id} ({dt}) "
                        f"occurred before previous txn ({prev_dt})"
                    )
                prev_dt = dt

        # 4. Validate Abandoned Checkouts
        chk_ids: Set[str] = set()
        for chk in checkouts:
            if chk.checkout_id in chk_ids:
                res.add_error(f"Duplicate checkout ID: {chk.checkout_id}")
            chk_ids.add(chk.checkout_id)

            if chk.customer_id not in customer_ids:
                res.add_error(f"Checkout {chk.checkout_id} references non-existent customer {chk.customer_id}")

            if chk.amount <= 0.0:
                res.add_error(f"Checkout {chk.checkout_id} has invalid non-positive amount: {chk.amount}")

            if not chk.is_abandoned:
                res.add_error(f"AbandonedCheckout {chk.checkout_id} has is_abandoned=False")

            chk_dict = chk.model_dump()
            for key in chk_dict:
                if key.startswith("ground_truth_") or key == "counterfactual_outcomes":
                    res.add_error(f"CRITICAL GROUND TRUTH LEAKAGE in checkout {chk.checkout_id}: field {key}")

        # 5. Validate Ground Truth Records
        gt_event_ids: Set[str] = set()
        for gt in ground_truth_records:
            if gt.event_id in gt_event_ids:
                res.add_error(f"Duplicate ground truth event ID: {gt.event_id}")
            gt_event_ids.add(gt.event_id)

            if gt.event_id not in txn_ids and gt.event_id not in chk_ids:
                res.add_error(f"Ground truth record references unknown event ID: {gt.event_id}")

            if not (0.0 <= gt.ground_truth_recovery_probability <= 1.0):
                res.add_error(f"Ground truth {gt.event_id} invalid recovery probability: {gt.ground_truth_recovery_probability}")

            if not (0.0 <= gt.ground_truth_customer_friction <= 1.0):
                res.add_error(f"Ground truth {gt.event_id} invalid customer friction: {gt.ground_truth_customer_friction}")

            if not gt.counterfactual_outcomes:
                res.add_error(f"Ground truth {gt.event_id} has empty counterfactual outcomes")

        return res

    @classmethod
    def _validate_failure_semantics(cls, txn: Transaction, res: ValidationResult):
        f = txn.failure_details
        cat = f.failure_category

        # Check semantic consistency
        if cat == FailureCategory.TRANSIENT_GATEWAY_FAILURE:
            if f.error_source not in (ErrorSource.GATEWAY, ErrorSource.NETWORK):
                res.add_error(f"Txn {txn.transaction_id}: TRANSIENT_GATEWAY_FAILURE has invalid source {f.error_source}")
            if f.error_reason != ErrorReason.TIMEOUT:
                res.add_error(f"Txn {txn.transaction_id}: TRANSIENT_GATEWAY_FAILURE has invalid reason {f.error_reason}")

        elif cat == FailureCategory.INSUFFICIENT_FUNDS:
            if f.error_reason != ErrorReason.INSUFFICIENT_FUNDS:
                res.add_error(f"Txn {txn.transaction_id}: INSUFFICIENT_FUNDS category has reason {f.error_reason}")

        elif cat == FailureCategory.AUTHENTICATION_FAILURE:
            if f.error_step != ErrorStep.PAYMENT_AUTHENTICATION or f.error_reason != ErrorReason.AUTHENTICATION_FAILED:
                res.add_error(f"Txn {txn.transaction_id}: AUTHENTICATION_FAILURE has inconsistent step/reason")

        elif cat == FailureCategory.HIGH_RISK:
            if f.error_reason != ErrorReason.RISK_DETECTED:
                res.add_error(f"Txn {txn.transaction_id}: HIGH_RISK has reason {f.error_reason}")
