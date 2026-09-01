"""
CLI Batch Inference Tool for REVIVE Diagnosis & Recovery Scoring Engine.
Usage:
    python -m agent.cli --dataset data/ --output data/revive_analysis/
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure UTF-8 stdout across all console environments
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent.engine import ReviveEngine
from evaluation.pipeline import DatasetLoader
from simulator.enums import PaymentStatus


def main():
    parser = argparse.ArgumentParser(description="REVIVE Diagnosis & Recovery Scoring Batch Processor")
    parser.add_argument("--dataset", "-d", type=str, default="data", help="Directory containing dataset .jsonl files")
    parser.add_argument("--output", "-o", type=str, default="data/revive_analysis", help="Output directory for recommendations and summary")

    args = parser.parse_args()
    data_path = Path(args.dataset)

    print(f"[*] Loading dataset from {data_path.resolve()}...")
    customers_by_id, transactions, checkouts, _ = DatasetLoader.load(data_path)

    failed_txns = [t for t in transactions if t.status == PaymentStatus.FAILED]
    all_opportunities = failed_txns + checkouts
    all_opportunities.sort(key=lambda e: e.created_at)

    print(f"[*] Analyzing {len(all_opportunities):,} failure & checkout opportunities with REVIVE Engine...")

    t0 = time.perf_counter()
    recommendations, summary = ReviveEngine.evaluate_batch(all_opportunities, customers_by_id)
    t1 = time.perf_counter()
    elapsed = t1 - t0
    rate = len(all_opportunities) / elapsed if elapsed > 0 else 0.0

    # Format Summary Report
    print("\n" + "=" * 70)
    print("           REVIVE DIAGNOSIS & RECOVERY SCORING REPORT           ")
    print("=" * 70)
    print(f"Opportunities Processed       : {summary.total_opportunities:,}")
    print(f"Execution Latency             : {elapsed * 1000:.2f} ms ({rate:,.1f} opportunities/sec)")
    print(f"Average Recoverability Score  : {summary.average_recoverability_score * 100:.2f}%")
    print(f"Average Diagnosis Confidence  : {summary.average_diagnosis_confidence * 100:.2f}%")
    print("-" * 70)
    print("RECOVERABILITY TIERS:")
    for tier, cnt in summary.recoverability_tier_distribution.items():
        pct = cnt / summary.total_opportunities * 100
        print(f"  {tier:<10}: {pct:5.1f}%  ({cnt:,})")
    print("-" * 70)
    print("RECOMMENDED RECOVERY ACTIONS:")
    for act, cnt in sorted(summary.recommended_action_distribution.items(), key=lambda x: x[1], reverse=True):
        pct = cnt / summary.total_opportunities * 100
        print(f"  {act:<15}: {pct:5.1f}%  ({cnt:,})")
    print("-" * 70)
    print("FAILURE DIAGNOSIS BREAKDOWN:")
    for cat, cnt in sorted(summary.diagnosis_distribution.items(), key=lambda x: x[1], reverse=True):
        pct = cnt / summary.total_opportunities * 100
        print(f"  {cat:<20}: {pct:5.1f}%  ({cnt:,})")
    print("-" * 70)
    print("RISK SIGNAL DISTRIBUTION:")
    for risk, cnt in sorted(summary.risk_signal_distribution.items(), key=lambda x: x[1], reverse=True):
        pct = cnt / summary.total_opportunities * 100
        print(f"  {risk:<10}: {pct:5.1f}%  ({cnt:,})")
    print("=" * 70 + "\n")

    # Write Output
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_file = out_dir / "batch_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(summary.model_dump_json(indent=2))

    recs_file = out_dir / "recommendations.jsonl"
    with open(recs_file, "w", encoding="utf-8") as f:
        for r in recommendations:
            f.write(r.model_dump_json() + "\n")

    print(f"[+] Output written to {out_dir.resolve()}")


if __name__ == "__main__":
    main()
