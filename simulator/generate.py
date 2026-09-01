"""
CLI generator for the REVIVE synthetic payment simulation environment.
Usage:
    python -m simulator.generate --transactions 10000 --seed 42 --output data/
"""

import argparse
import json
import os
import random
import sys
from pathlib import Path
from typing import List, Dict

# Ensure UTF-8 stdout for international symbols across all console environments
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from simulator.checkout_generator import CheckoutGenerator
from simulator.config import SimulatorConfig
from simulator.customer_generator import CustomerGenerator
from simulator.ground_truth_engine import GroundTruthEngine
from simulator.ground_truth_schema import GroundTruthRecord
from simulator.public_schema import AbandonedCheckout, Customer, Transaction
from simulator.summary import DatasetSummary
from simulator.transaction_generator import TransactionGenerator
from simulator.validator import DatasetValidator


def generate_dataset(
    transaction_count: int = 10000,
    customer_count: int | None = None,
    seed: int = 42,
    output_dir: Path | str = "data",
    config_path: Path | str | None = None
) -> Dict[str, any]:
    """Generates, validates, and persists a complete synthetic payment dataset."""
    
    # 1. Load configuration
    config = SimulatorConfig.from_yaml(config_path)
    config.transaction_count = transaction_count
    config.random_seed = seed
    if customer_count:
        config.customer_count = customer_count
    else:
        # Scale customers proportionally (~1 customer per 5 transactions, min 50)
        config.customer_count = max(50, transaction_count // 5)

    rng = random.Random(seed)

    print(f"[*] Initializing REVIVE Simulator (seed={seed}, target_txns={transaction_count:,}, custs={config.customer_count:,})...")

    # 2. Generate Customers
    cust_gen = CustomerGenerator(config, rng)
    customers: List[Customer] = cust_gen.generate_population(config.customer_count)
    customers_by_id = {c.customer_id: c for c in customers}

    # 3. Generate Transactions
    txn_gen = TransactionGenerator(config, rng)
    transactions: List[Transaction] = txn_gen.generate_transactions(customers, target_transaction_count=transaction_count)

    # 4. Generate Abandoned Checkouts
    chk_gen = CheckoutGenerator(config, rng)
    checkouts: List[AbandonedCheckout] = chk_gen.generate_abandoned_checkouts(customers)

    # 5. Generate Evaluation Ground Truth
    gt_engine = GroundTruthEngine(config, rng)
    txn_gt = gt_engine.generate_ground_truth_for_transactions(transactions, customers_by_id)
    chk_gt = gt_engine.generate_ground_truth_for_checkouts(checkouts, customers_by_id)
    all_ground_truth: List[GroundTruthRecord] = txn_gt + chk_gt

    # 6. Validate Dataset Integrity & Absence of Leakage
    print("[*] Running automated dataset integrity & zero-leakage validator...")
    val_res = DatasetValidator.validate(customers, transactions, checkouts, all_ground_truth)
    if not val_res.is_valid:
        print("[!] DATASET VALIDATION FAILED:")
        for err in val_res.errors[:20]:
            print(f"  - {err}")
        if len(val_res.errors) > 20:
            print(f"  ... and {len(val_res.errors) - 20} more errors")
        sys.exit(1)

    print(f"[+] Validation Passed! (0 errors, {len(val_res.warnings)} warnings)")

    # 7. Write Datasets to Disk (JSONL)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    cust_file = out_path / "customers.jsonl"
    txn_file = out_path / "transactions.jsonl"
    chk_file = out_path / "abandoned_checkouts.jsonl"
    gt_file = out_path / "ground_truth.jsonl"

    print(f"[*] Writing dataset files to {out_path.resolve()}...")
    with open(cust_file, "w", encoding="utf-8") as f:
        for c in customers:
            f.write(c.model_dump_json() + "\n")

    with open(txn_file, "w", encoding="utf-8") as f:
        for t in transactions:
            f.write(t.model_dump_json() + "\n")

    with open(chk_file, "w", encoding="utf-8") as f:
        for chk in checkouts:
            f.write(chk.model_dump_json() + "\n")

    with open(gt_file, "w", encoding="utf-8") as f:
        for gt in all_ground_truth:
            f.write(gt.model_dump_json() + "\n")

    # 8. Compute and Output Summary Statistics
    summary = DatasetSummary.compute(customers, transactions, checkouts, all_ground_truth)
    report = DatasetSummary.format_report(summary)
    print("\n" + report + "\n")

    # Save summary metadata
    with open(out_path / "dataset_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


def main():
    parser = argparse.ArgumentParser(description="REVIVE Synthetic Payment & Customer Lifecycle Simulator CLI")
    parser.add_argument("--transactions", "-t", type=int, default=10000, help="Target number of transactions (default: 10000)")
    parser.add_argument("--customers", "-c", type=int, default=None, help="Number of customer profiles to generate")
    parser.add_argument("--seed", "-s", type=int, default=42, help="Deterministic random seed (default: 42)")
    parser.add_argument("--output", "-o", type=str, default="data", help="Output directory for generated datasets (default: data)")
    parser.add_argument("--config", type=str, default=None, help="Optional custom YAML config path")

    args = parser.parse_args()
    generate_dataset(
        transaction_count=args.transactions,
        customer_count=args.customers,
        seed=args.seed,
        output_dir=args.output,
        config_path=args.config
    )


if __name__ == "__main__":
    main()
