"""
CLI Tool for Controlled Recovery Execution Simulator and Trace Inspection.
Usage:
    python -m execution.cli --dataset data/ --output data/execution_analysis/
    python -m execution.cli --dataset data/ --trace-event txn_00000018
"""

import argparse
import csv
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

from evaluation.pipeline import DatasetLoader
from execution.batch import BatchExecutionRunner
from execution.orchestrator import ReviveOrchestrator
from simulator.enums import PaymentStatus


def main():
    parser = argparse.ArgumentParser(description="REVIVE Controlled Recovery Execution Simulator")
    parser.add_argument("--dataset", "-d", type=str, default="data", help="Directory containing dataset .jsonl files")
    parser.add_argument("--output", "-o", type=str, default="data/execution_analysis", help="Output directory for execution traces and summary")
    parser.add_argument("--trace-event", "-t", type=str, default=None, help="Inspect full end-to-end lifecycle trace for a specific event_id")

    args = parser.parse_args()
    data_path = Path(args.dataset)

    print(f"[*] Loading dataset from {data_path.resolve()}...")
    customers_by_id, transactions, checkouts, gt_map = DatasetLoader.load(data_path)

    failed_txns = [t for t in transactions if t.status == PaymentStatus.FAILED]
    all_opportunities = failed_txns + checkouts
    all_opportunities.sort(key=lambda e: e.created_at)

    # --------------------------------------------------------------------------
    # Single Event Trace Mode
    # --------------------------------------------------------------------------
    if args.trace_event:
        target_event = next((e for e in all_opportunities if (getattr(e, "transaction_id", None) == args.trace_event or getattr(e, "checkout_id", None) == args.trace_event)), None)
        if not target_event:
            print(f"[!] Event '{args.trace_event}' not found in dataset.")
            sys.exit(1)

        orch = ReviveOrchestrator()
        cust = customers_by_id.get(target_event.customer_id)
        gt = gt_map.get(args.trace_event)
        trace = orch.process_event(target_event, customer=cust, ground_truth=gt)

        print("\n" + "=" * 80)
        print(f"               REVIVE LIFECYCLE TRACE: {args.trace_event}               ")
        print("=" * 80)
        print(f"Event ID              : {trace.event_id}")
        print(f"Customer ID           : {trace.customer_id}")
        print(f"Amount                : INR {trace.recommendation.amount:,.2f}")
        print(f"Diagnosis             : {trace.recommendation.diagnosis.category.value} (Confidence: {trace.recommendation.diagnosis.confidence * 100:.1f}%)")
        print(f"Recoverability Score  : {trace.recommendation.recoverability_score * 100:.1f}% ({trace.recommendation.recoverability_tier.value})")
        print(f"Recommended Action    : {trace.recommendation.recommended_action.value}")
        print("-" * 80)
        print(f"Policy Decision       : {trace.policy_decision.decision.value} (Rule: {trace.policy_decision.primary_rule_id.value})")
        print(f"Policy Reason         : {trace.policy_decision.reason}")
        if trace.policy_decision.execution_authorization:
            auth = trace.policy_decision.execution_authorization
            print(f"Authorization ID      : {auth.authorization_id} (Version: {auth.policy_version})")
        print("-" * 80)
        print(f"Execution Status      : {trace.execution_result.execution_status.value}")
        print(f"Execution Reason      : {trace.execution_result.execution_reason}")
        print(f"External Reference    : {trace.execution_result.simulated_external_reference}")
        print(f"Recovery Outcome      : {trace.execution_result.recovery_outcome.value}")
        print(f"Recovered Amount      : INR {trace.execution_result.recovered_amount:,.2f}")
        print("-" * 80)
        print("AUDIT TRAIL:")
        for a in trace.audit_events:
            print(f"  [{a.timestamp}] {a.event_type.value:<25} - {json.dumps(a.details)}")
        print("=" * 80 + "\n")
        sys.exit(0)

    # --------------------------------------------------------------------------
    # Batch Execution Mode
    # --------------------------------------------------------------------------
    print(f"[*] Executing controlled simulated recovery across {len(all_opportunities):,} opportunities...")

    runner = BatchExecutionRunner()
    t0 = time.perf_counter()
    traces, summary = runner.run_batch(
        events=all_opportunities,
        customers_by_id=customers_by_id,
        ground_truth_map=gt_map,
        total_transactions=len(transactions)
    )
    t1 = time.perf_counter()
    elapsed = t1 - t0
    rate = len(all_opportunities) / elapsed if elapsed > 0 else 0.0

    # Format Summary Report
    print("\n" + "=" * 80)
    print("         REVIVE CONTROLLED RECOVERY EXECUTION SIMULATOR REPORT          ")
    print("=" * 80)
    print(f"Total Transactions Evaluated   : {summary.total_transactions:,}")
    print(f"Failure Opportunities Analyzed : {summary.total_failed_opportunities:,}")
    print(f"Execution Latency              : {elapsed * 1000:.2f} ms ({rate:,.1f} opps/sec)")
    print("-" * 80)
    print("POLICY & EXECUTION GATING:")
    print(f"  Policy Authorized (ALLOW)    : {summary.policy_authorized_count:,} ({summary.policy_authorized_count / summary.total_failed_opportunities * 100:.1f}%)")
    print(f"  Human Review Escalations     : {summary.policy_human_review_count:,} ({summary.policy_human_review_count / summary.total_failed_opportunities * 100:.1f}%)")
    print(f"  Passive / No Action          : {summary.policy_no_action_count:,} ({summary.policy_no_action_count / summary.total_failed_opportunities * 100:.1f}%)")
    print(f"  Policy Denied                : {summary.policy_denied_count:,}")
    print(f"  Actions Successfully Executed: {summary.actions_executed_count:,}")
    print(f"  Actions Blocked at Executor  : {summary.actions_blocked_count:,}")
    print("-" * 80)
    print("FINANCIAL RECOVERY PERFORMANCE (INR):")
    print(f"  Revenue at Risk              : INR {summary.total_revenue_at_risk:>12,.2f}")
    print(f"  Natural Recovery (NO_ACTION) : INR {summary.natural_recovery_revenue:>12,.2f}")
    print(f"  REVIVE Total Recovered       : INR {summary.total_recovered_revenue:>12,.2f}")
    print(f"  Incremental Revenue Uplift   : INR {summary.incremental_recovered_revenue:>12,.2f}")
    print(f"  Intervention Success Rate    : {summary.intervention_success_rate * 100:>11.1f}%")
    print(f"  Overall Opportunity Capture  : {summary.overall_recovery_rate * 100:>11.1f}%")
    print("-" * 80)
    print("ACTION-LEVEL BREAKDOWN:")
    print(f"{'Action':<15} | {'Recommended':<12} | {'Authorized':<11} | {'Executed':<9} | {'Recovered (INR)':<16} | {'Success Rate'}")
    print("-" * 80)
    for act_name, st in summary.action_breakdown.items():
        if st.recommended_count > 0:
            print(
                f"{act_name:<15} | "
                f"{st.recommended_count:>12,d} | "
                f"{st.authorized_count:>11,d} | "
                f"{st.executed_count:>9,d} | "
                f"INR {st.recovered_revenue:>12,.2f} | "
                f"{st.intervention_success_rate * 100:>11.1f}%"
            )
    print("-" * 80)
    print("SAFETY METRICS:")
    for k, v in summary.safety_metrics.items():
        print(f"  {k.replace('_', ' ').title():<35}: {v:,}")
    print("=" * 80 + "\n")

    # Write Outputs
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_file = out_dir / "execution_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(summary.model_dump_json(indent=2))

    traces_file = out_dir / "execution_traces.jsonl"
    with open(traces_file, "w", encoding="utf-8") as f:
        for t in traces:
            f.write(t.model_dump_json() + "\n")

    csv_file = out_dir / "action_breakdown.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Action", "Recommended", "Authorized", "Executed", "Blocked", "RecoveredCount", "RecoveredRevenueINR", "InterventionSuccessRate"])
        for act, st in summary.action_breakdown.items():
            writer.writerow([st.action, st.recommended_count, st.authorized_count, st.executed_count, st.blocked_count, st.recovered_count, st.recovered_revenue, st.intervention_success_rate])

    print(f"[+] Output written to {out_dir.resolve()}")


if __name__ == "__main__":
    main()
