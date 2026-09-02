"""
CLI Command for Running Experimental Holdout Evaluation & Multi-Seed Benchmarks.
Usage:
    python -m evaluation.experiment.cli --output experiments/ --seeds 101,202,303,404,505 --size 10000
"""

import argparse
import sys
import time
from pathlib import Path

# Ensure UTF-8 stdout across all console environments
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from evaluation.experiment.config import ExperimentConfig
from evaluation.experiment.reporter import BenchmarkReporter
from evaluation.experiment.runner import ExperimentRunner


def main():
    parser = argparse.ArgumentParser(description="REVIVE Experimental Evaluation & Holdout Benchmarking System")
    parser.add_argument("--output", "-o", type=str, default="experiments/benchmark_run_001", help="Output directory for experiment artifacts")
    parser.add_argument("--seeds", "-s", type=str, default="101,202,303,404,505", help="Comma-separated list of evaluation seeds")
    parser.add_argument("--size", "-n", type=int, default=10000, help="Transactions per evaluation dataset")
    parser.add_argument("--bootstrap", "-b", type=int, default=1000, help="Number of bootstrap resamples")

    args = parser.parse_args()

    eval_seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    config = ExperimentConfig(
        eval_seeds=eval_seeds,
        eval_transaction_count=args.size,
        bootstrap_samples=args.bootstrap
    )

    print(f"[*] Starting REVIVE Experimental Evaluation across {len(eval_seeds)} holdout seeds ({eval_seeds})...")
    print(f"[*] Dataset Size per Seed: {config.eval_transaction_count:,} transactions")
    print(f"[*] Bootstrap Iterations : {config.bootstrap_samples:,} (95% CI)")

    runner = ExperimentRunner(config)
    t0 = time.perf_counter()
    report, seed_results = runner.run_experiment()
    t1 = time.perf_counter()
    elapsed = t1 - t0

    out_dir = Path(args.output)
    BenchmarkReporter.export_artifacts(report, seed_results, config, out_dir)

    revive_stats = report.strategy_aggregates.get("REVIVE", {})
    no_action_stats = report.strategy_aggregates.get("NO_ACTION", {})
    naive_retry_stats = report.strategy_aggregates.get("NAIVE_RETRY", {})
    rule_based_stats = report.strategy_aggregates.get("RULE_BASED", {})

    print("\n" + "=" * 80)
    print("        REVIVE MULTI-SEED HOLDOUT BENCHMARK SUMMARY (SYNTHETIC)         ")
    print("=" * 80)
    print(f"Evaluation Completed In        : {elapsed:.2f} s across {len(eval_seeds)} seeds")
    print(f"Total Transactions Benchmarked : {len(eval_seeds) * config.eval_transaction_count:,}")
    print("-" * 80)
    print(f"{'Strategy':<15} | {'Mean Recovered (INR)':<20} | {'Incremental Revenue':<20} | {'Precision'}")
    print("-" * 80)
    print(f"{'NO_ACTION':<15} | INR {no_action_stats.get('recovered_revenue').mean:>16,.2f} | INR {0.0:>16,.2f} | {'N/A':>9}")
    print(f"{'NAIVE_RETRY':<15} | INR {naive_retry_stats.get('recovered_revenue').mean:>16,.2f} | INR {naive_retry_stats.get('incremental_revenue').mean:>16,.2f} | {naive_retry_stats.get('intervention_precision').mean * 100:>8.1f}%")
    print(f"{'RULE_BASED':<15} | INR {rule_based_stats.get('recovered_revenue').mean:>16,.2f} | INR {rule_based_stats.get('incremental_revenue').mean:>16,.2f} | {rule_based_stats.get('intervention_precision').mean * 100:>8.1f}%")
    print(f"{'REVIVE (Ours)':<15} | INR {revive_stats.get('recovered_revenue').mean:>16,.2f} | INR {revive_stats.get('incremental_revenue').mean:>16,.2f} | {revive_stats.get('intervention_precision').mean * 100:>8.1f}%")
    print("-" * 80)
    print(f"Recoverability Brier Score     : {report.calibration.brier_score:.4f}")
    print(f"Expected Calibration Error     : {report.calibration.expected_calibration_error * 100:.2f}%")
    print(f"Accounting Invariants Balanced : {report.accounting_verified}")
    print(f"[+] Full Report Written to     : {(out_dir / 'BENCHMARK_REPORT.md').resolve()}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
