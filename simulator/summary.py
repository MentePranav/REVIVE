"""
Statistical summary calculator for generated synthetic payment datasets.
Computes real mathematical distributions, metrics, and failure category breakdowns.
"""

import statistics
from typing import List, Dict, Any

from simulator.enums import PaymentMethod, PaymentStatus, FailureCategory
from simulator.ground_truth_schema import GroundTruthRecord
from simulator.public_schema import AbandonedCheckout, Customer, Transaction


class DatasetSummary:
    """Calculates and formats actual summary statistics from a generated dataset."""

    @classmethod
    def compute(
        cls,
        customers: List[Customer],
        transactions: List[Transaction],
        checkouts: List[AbandonedCheckout],
        ground_truth: List[GroundTruthRecord]
    ) -> Dict[str, Any]:
        total_txns = len(transactions)
        total_custs = len(customers)
        total_checkouts = len(checkouts)

        # Status counts
        status_counts = {
            PaymentStatus.SUCCESS.value: 0,
            PaymentStatus.FAILED.value: 0,
            PaymentStatus.ABANDONED.value: total_checkouts
        }
        for t in transactions:
            if t.status == PaymentStatus.SUCCESS:
                status_counts[PaymentStatus.SUCCESS.value] += 1
            elif t.status == PaymentStatus.FAILED:
                status_counts[PaymentStatus.FAILED.value] += 1

        total_volume = total_txns + total_checkouts
        status_pct = {
            k: (v / total_volume * 100.0) if total_volume > 0 else 0.0
            for k, v in status_counts.items()
        }

        # Amounts
        all_amounts = [t.amount for t in transactions] + [c.amount for c in checkouts]
        avg_amt = statistics.mean(all_amounts) if all_amounts else 0.0
        med_amt = statistics.median(all_amounts) if all_amounts else 0.0

        # Payment Methods
        method_counts = {m.value: 0 for m in PaymentMethod}
        for t in transactions:
            method_counts[t.payment_method.value] += 1
        for c in checkouts:
            if c.payment_method_selected:
                method_counts[c.payment_method_selected.value] += 1

        total_method_events = sum(method_counts.values())
        method_pct = {
            k: (v / total_method_events * 100.0) if total_method_events > 0 else 0.0
            for k, v in method_counts.items()
        }

        # Failure categories
        cat_counts: Dict[str, int] = {}
        for t in transactions:
            if t.status == PaymentStatus.FAILED and t.failure_details:
                cat_name = t.failure_details.failure_category.value
                cat_counts[cat_name] = cat_counts.get(cat_name, 0) + 1

        # Recoverability
        recoverable_count = sum(1 for gt in ground_truth if gt.ground_truth_recoverable)
        resolved_count = sum(1 for gt in ground_truth if gt.is_already_resolved)

        return {
            "transaction_count": total_txns,
            "customer_count": total_custs,
            "checkout_count": total_checkouts,
            "status_counts": status_counts,
            "status_percentages": status_pct,
            "average_amount": round(avg_amt, 2),
            "median_amount": round(med_amt, 2),
            "method_counts": method_counts,
            "method_percentages": method_pct,
            "failure_category_counts": cat_counts,
            "recoverable_opportunities": recoverable_count,
            "already_resolved_count": resolved_count,
            "total_ground_truth_events": len(ground_truth)
        }

    @classmethod
    def format_report(cls, summary: Dict[str, Any]) -> str:
        lines = [
            "=================================================================",
            "                 REVIVE SYNTHETIC DATASET REPORT                 ",
            "=================================================================",
            f"Transactions Generated : {summary['transaction_count']:,}",
            f"Customers Modeled      : {summary['customer_count']:,}",
            f"Abandoned Checkouts    : {summary['checkout_count']:,}",
            "-----------------------------------------------------------------",
            "STATUS DISTRIBUTION (Combined Funnel):",
            f"  SUCCESS   : {summary['status_percentages']['SUCCESS']:5.1f}%  ({summary['status_counts']['SUCCESS']:,})",
            f"  FAILED    : {summary['status_percentages']['FAILED']:5.1f}%  ({summary['status_counts']['FAILED']:,})",
            f"  ABANDONED : {summary['status_percentages']['ABANDONED']:5.1f}%  ({summary['status_counts']['ABANDONED']:,})",
            "-----------------------------------------------------------------",
            f"Average Transaction Amount : INR {summary['average_amount']:,.2f}",
            f"Median Transaction Amount  : INR {summary['median_amount']:,.2f}",
            "-----------------------------------------------------------------",
            "PAYMENT METHOD BREAKDOWN:",
            f"  UPI        : {summary['method_percentages']['UPI']:5.1f}%  ({summary['method_counts']['UPI']:,})",
            f"  CARD       : {summary['method_percentages']['CARD']:5.1f}%  ({summary['method_counts']['CARD']:,})",
            f"  NETBANKING : {summary['method_percentages']['NETBANKING']:5.1f}%  ({summary['method_counts']['NETBANKING']:,})",
            f"  WALLET     : {summary['method_percentages']['WALLET']:5.1f}%  ({summary['method_counts']['WALLET']:,})",
            "-----------------------------------------------------------------",
            f"RECOVERABILITY GROUND TRUTH (Evaluation Benchmark):",
            f"  Total Eligible Failure Events : {summary['total_ground_truth_events']:,}",
            f"  True Recoverable Opportunities : {summary['recoverable_opportunities']:,} ({(summary['recoverable_opportunities'] / max(1, summary['total_ground_truth_events']) * 100):.1f}%)",
            f"  Organically Resolved Events   : {summary['already_resolved_count']:,}",
            "-----------------------------------------------------------------",
            "FAILURE CATEGORIES (Failed Transactions):"
        ]

        for cat, count in sorted(summary["failure_category_counts"].items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {cat:<30}: {count:,}")

        lines.append("=================================================================")
        return "\n".join(lines)
