"""
CLI benchmark comparison harness for all REVIVE recovery strategies.
Usage:
    python -m evaluation.compare --dataset data/ --output data/evaluations/
"""

import argparse
import csv
import sys
from pathlib import Path

# Ensure UTF-8 stdout across all console environments
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from evaluation.pipeline import EvaluationPipeline
from evaluation.strategies import NaiveRetryStrategy, NoActionStrategy, RuleBasedStrategy


def main():
    parser = argparse.ArgumentParser(description="Run Comparative Benchmark across all Revenue Recovery Strategies")
    parser.add_argument("--dataset", "-d", type=str, default="data", help="Path to directory containing dataset .jsonl files")
    parser.add_argument("--output", "-o", type=str, default="data/evaluations", help="Output directory for benchmark summary & logs")

    args = parser.parse_args()
    strategies = [
        NoActionStrategy(),
        NaiveRetryStrategy(),
        RuleBasedStrategy(),
    ]

    pipeline = EvaluationPipeline()
    print(f"[*] Executing benchmark comparison on dataset: {Path(args.dataset).resolve()}...")

    comparison = pipeline.run_benchmark_comparison(
        strategies=strategies,
        data_dir=args.dataset,
        output_dir=args.output
    )

    # Format Console Comparison Report
    print("\n" + "=" * 90)
    print("                     REVIVE REVENUE RECOVERY BASELINE BENCHMARK                     ")
    print("=" * 90)
    header = f"{'Strategy':<16} | {'Recovered (INR)':<16} | {'Incremental':<14} | {'Interventions':<14} | {'Precision':<10} | {'Capture Rate'}"
    print(header)
    print("-" * 90)

    for name, m in comparison.strategy_metrics.items():
        row = (
            f"{name:<16} | "
            f"INR {m.recovered_revenue:>12,.2f} | "
            f"INR {m.incremental_revenue:>10,.2f} | "
            f"{m.total_interventions_attempted:>14,d} | "
            f"{m.intervention_precision * 100:>9.1f}% | "
            f"{m.recoverable_opportunity_capture_rate * 100:>11.1f}%"
        )
        print(row)

    print("=" * 90 + "\n")

    # Write CSV Export
    out_path = Path(args.output)
    csv_file = out_path / "benchmark_comparison.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Strategy",
            "Total Transactions",
            "Eligible Opportunities",
            "Interventions Attempted",
            "Successful Recoveries",
            "Revenue at Risk (INR)",
            "Natural Recovery (INR)",
            "Recovered Revenue (INR)",
            "Incremental Revenue (INR)",
            "Intervention Precision",
            "Recoverable Capture Rate",
            "False Positive Rate",
            "Action Costs (INR)",
            "Net Incremental Value (INR)"
        ])
        for name, m in comparison.strategy_metrics.items():
            writer.writerow([
                name,
                m.total_transactions_evaluated,
                m.total_eligible_opportunities,
                m.total_interventions_attempted,
                m.successful_recoveries,
                m.revenue_at_risk,
                m.natural_recovery_revenue,
                m.recovered_revenue,
                m.incremental_revenue,
                m.intervention_precision,
                m.recoverable_opportunity_capture_rate,
                m.false_positive_rate,
                m.total_action_costs,
                m.net_incremental_value
            ])

    print(f"[+] Benchmark summary saved to {out_path / 'benchmark_summary.json'}")
    print(f"[+] Benchmark CSV table saved to {csv_file}")


if __name__ == "__main__":
    main()
