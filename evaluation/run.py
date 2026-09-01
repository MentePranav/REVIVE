"""
CLI entry point for evaluating a single recovery strategy.
Usage:
    python -m evaluation.run --strategy rule_based --dataset data/
"""

import argparse
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


def get_strategy(name: str):
    name_clean = name.strip().upper()
    if name_clean in ("NO_ACTION", "NOACTION", "PASSIVE"):
        return NoActionStrategy()
    elif name_clean in ("NAIVE_RETRY", "NAIVERETRY", "RETRY"):
        return NaiveRetryStrategy()
    elif name_clean in ("RULE_BASED", "RULEBASED", "RULES"):
        return RuleBasedStrategy()
    else:
        raise ValueError(f"Unknown strategy: '{name}'. Supported: 'no_action', 'naive_retry', 'rule_based'")


def main():
    parser = argparse.ArgumentParser(description="Evaluate a Single Revenue Recovery Strategy on a Synthetic Dataset")
    parser.add_argument("--strategy", "-s", type=str, required=True, help="Strategy name (no_action | naive_retry | rule_based)")
    parser.add_argument("--dataset", "-d", type=str, default="data", help="Path to directory containing dataset .jsonl files")
    parser.add_argument("--output", "-o", type=str, default="data/evaluations", help="Output directory for evaluation results")

    args = parser.parse_args()
    strategy = get_strategy(args.strategy)
    pipeline = EvaluationPipeline()

    print(f"[*] Running evaluation for strategy: {strategy.name} on dataset: {Path(args.dataset).resolve()}...")
    
    # Establish natural recovery first if not NO_ACTION
    natural_rev = 0.0
    if strategy.name != "NO_ACTION":
        no_action = NoActionStrategy()
        m_na, _ = pipeline.evaluate_strategy(no_action, args.dataset, natural_recovery_rev=0.0)
        natural_rev = m_na.recovered_revenue

    metrics, records = pipeline.evaluate_strategy(strategy, args.dataset, natural_recovery_rev=natural_rev)

    # Print summary
    print("\n" + "=" * 65)
    print(f"         REVIVE STRATEGY EVALUATION: {metrics.strategy_name}         ")
    print("=" * 65)
    print(f"Total Transactions Evaluated     : {metrics.total_transactions_evaluated:,}")
    print(f"Failed Transactions Considered   : {metrics.failed_transactions_considered:,}")
    print(f"Abandoned Checkouts Considered   : {metrics.abandoned_checkouts_considered:,}")
    print(f"Total Eligible Opportunities     : {metrics.total_eligible_opportunities:,}")
    print("-" * 65)
    print(f"Total Interventions Attempted    : {metrics.total_interventions_attempted:,}")
    print(f"Successful Recoveries Captured   : {metrics.successful_recoveries:,}")
    print(f"Intervention Precision           : {metrics.intervention_precision * 100:.2f}%")
    print(f"Recoverable Capture Rate (Eval)  : {metrics.recoverable_opportunity_capture_rate * 100:.2f}%")
    print(f"False Positive Action Rate       : {metrics.false_positive_rate * 100:.2f}%")
    print("-" * 65)
    print(f"Revenue at Risk                  : INR {metrics.revenue_at_risk:,.2f}")
    print(f"Natural Recovery Revenue         : INR {metrics.natural_recovery_revenue:,.2f}")
    print(f"Total Revenue Recovered          : INR {metrics.recovered_revenue:,.2f}")
    print(f"Incremental Revenue Uplift       : INR {metrics.incremental_revenue:,.2f}")
    print(f"Total Action Execution Costs     : INR {metrics.total_action_costs:,.2f}")
    print(f"Net Incremental Economic Value   : INR {metrics.net_incremental_value:,.2f}")
    print("=" * 65 + "\n")

    # Save output
    out_path = Path(args.output)
    out_path.mkdir(parents=True, exist_ok=True)
    summary_file = out_path / f"metrics_{strategy.name.lower()}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(metrics.model_dump_json(indent=2))

    log_file = out_path / f"decisions_{strategy.name.lower()}.jsonl"
    with open(log_file, "w", encoding="utf-8") as f:
        for r in records:
            f.write(r.model_dump_json() + "\n")
    print(f"[+] Results saved to {out_path.resolve()}")


if __name__ == "__main__":
    main()
