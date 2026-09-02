"""
Dataset Splitter and Holdout Environment Generator for REVIVE Phase 7.
Ensures strict segregation between development and unseen holdout evaluation datasets.
"""

import random
from typing import Dict, List, Optional
from simulator.checkout_generator import CheckoutGenerator
from simulator.config import SimulatorConfig
from simulator.customer_generator import CustomerGenerator
from simulator.ground_truth_engine import GroundTruthEngine
from simulator.ground_truth_schema import GroundTruthRecord
from simulator.public_schema import AbandonedCheckout, Customer, Transaction
from simulator.transaction_generator import TransactionGenerator
from simulator.validator import DatasetValidator


class DatasetBundle:
    """Encapsulates a generated synthetic dataset and its isolated ground truth."""
    def __init__(
        self,
        seed: int,
        customers: List[Customer],
        transactions: List[Transaction],
        checkouts: List[AbandonedCheckout],
        ground_truth: List[GroundTruthRecord]
    ):
        self.seed = seed
        self.customers = customers
        self.transactions = transactions
        self.checkouts = checkouts
        self.ground_truth = ground_truth

        self.customers_by_id: Dict[str, Customer] = {c.customer_id: c for c in customers}
        self.ground_truth_map: Dict[str, GroundTruthRecord] = {g.event_id: g for g in ground_truth}

        self.failed_transactions: List[Transaction] = [t for t in transactions if t.status.value == "FAILED"]
        self.all_opportunities = self.failed_transactions + self.checkouts
        self.all_opportunities.sort(key=lambda e: e.created_at)


class DatasetSplitter:
    """Generates and manages development tuning sets and unseen holdout evaluation sets."""

    @staticmethod
    def _generate(seed: int, transaction_count: int, config_path: Optional[str] = None) -> DatasetBundle:
        config = SimulatorConfig.from_yaml(config_path)
        config.transaction_count = transaction_count
        config.random_seed = seed
        config.customer_count = max(50, transaction_count // 5)

        rng = random.Random(seed)

        # 1. Customers
        cust_gen = CustomerGenerator(config, rng)
        customers: List[Customer] = cust_gen.generate_population(config.customer_count)
        customers_by_id = {c.customer_id: c for c in customers}

        # 2. Transactions
        txn_gen = TransactionGenerator(config, rng)
        transactions: List[Transaction] = txn_gen.generate_transactions(customers, target_transaction_count=transaction_count)

        # 3. Checkouts
        chk_gen = CheckoutGenerator(config, rng)
        checkouts: List[AbandonedCheckout] = chk_gen.generate_abandoned_checkouts(customers)

        # 4. Ground Truth
        gt_engine = GroundTruthEngine(config, rng)
        txn_gt = gt_engine.generate_ground_truth_for_transactions(transactions, customers_by_id)
        chk_gt = gt_engine.generate_ground_truth_for_checkouts(checkouts, customers_by_id)
        all_ground_truth: List[GroundTruthRecord] = txn_gt + chk_gt

        # 5. Validation
        val_res = DatasetValidator.validate(customers, transactions, checkouts, all_ground_truth)
        if not val_res.is_valid:
            raise RuntimeError(f"Generated dataset validation failed: {val_res.errors[:5]}")

        return DatasetBundle(
            seed=seed,
            customers=customers,
            transactions=transactions,
            checkouts=checkouts,
            ground_truth=all_ground_truth
        )

    @staticmethod
    def generate_development_set(seed: int = 42, transaction_count: int = 2000) -> DatasetBundle:
        """Generates the development set used exclusively for parameter tuning and calibration freezing."""
        return DatasetSplitter._generate(seed=seed, transaction_count=transaction_count)

    @staticmethod
    def generate_evaluation_set(seed: int, transaction_count: int = 10000) -> DatasetBundle:
        """Generates an independent unseen holdout evaluation dataset."""
        return DatasetSplitter._generate(seed=seed, transaction_count=transaction_count)
