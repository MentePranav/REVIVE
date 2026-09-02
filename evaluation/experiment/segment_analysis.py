"""
Segment Analysis Engine for REVIVE Experimental Evaluation.
Analyzes recovery performance across fixed ticket size tiers, payment methods, failure categories, and customer segments.
"""

from typing import Dict, List, Tuple, Union
from evaluation.experiment.models import SegmentMetrics
from execution.models import ExecutionLifecycleTrace, ExecutionStatus, SimulatedRecoveryOutcome
from simulator.public_schema import AbandonedCheckout, Customer, Transaction


class SegmentAnalyzer:
    """Computes recovery and precision metrics across fixed, predefined operational segments."""

    @staticmethod
    def analyze(
        traces: List[ExecutionLifecycleTrace],
        events_by_id: Dict[str, Union[Transaction, AbandonedCheckout]],
        customers_by_id: Dict[str, Customer]
    ) -> List[SegmentMetrics]:
        results: List[SegmentMetrics] = []

        # Helper accumulators: (segment_type, segment_value) -> dict
        accumulators: Dict[Tuple[str, str], Dict[str, float]] = {}

        for t in traces:
            event = events_by_id.get(t.event_id)
            if not event:
                continue

            customer = customers_by_id.get(t.customer_id)
            amount = float(event.amount)
            is_attempted = (t.execution_result.execution_status == ExecutionStatus.EXECUTED)
            is_recovered = (t.execution_result.recovery_outcome in (SimulatedRecoveryOutcome.RECOVERED, SimulatedRecoveryOutcome.NATURAL_RECOVERY))
            recovered_amt = float(t.execution_result.recovered_amount) if is_recovered else 0.0

            # 1. Amount Tier Segment
            if amount < 1000.0:
                tier = "Micro (< INR 1,000)"
            elif amount < 5000.0:
                tier = "Small (INR 1,000 - 5,000)"
            elif amount < 25000.0:
                tier = "Medium (INR 5,000 - 25,000)"
            else:
                tier = "Large (>= INR 25,000)"

            # 2. Payment Method Segment
            if isinstance(event, Transaction):
                method = event.payment_method.value if hasattr(event.payment_method, "value") else str(event.payment_method)
            else:
                method = "CHECKOUT_DROP"

            # 3. Failure Category Segment
            if isinstance(event, Transaction) and event.failure_details:
                fc = event.failure_details.failure_category
                cat = fc.value if hasattr(fc, "value") else str(fc)
            else:
                cat = "USER_ABANDONMENT"

            # 4. Customer Segment
            c_seg = customer.customer_segment.value if customer and hasattr(customer.customer_segment, "value") else (customer.customer_segment if customer else "UNKNOWN")

            segment_keys = [
                ("amount_tier", tier),
                ("payment_method", method),
                ("failure_category", cat),
                ("customer_segment", c_seg),
            ]

            for s_type, s_val in segment_keys:
                acc = accumulators.setdefault((s_type, s_val), {
                    "total_ops": 0,
                    "rev_at_risk": 0.0,
                    "attempted": 0,
                    "recovered": 0,
                    "rec_rev": 0.0,
                })
                acc["total_ops"] += 1
                acc["rev_at_risk"] += amount
                if is_attempted:
                    acc["attempted"] += 1
                if is_recovered:
                    acc["recovered"] += 1
                    acc["rec_rev"] += recovered_amt

        for (s_type, s_val), data in sorted(accumulators.items()):
            ops = int(data["total_ops"])
            att = int(data["attempted"])
            rec = int(data["recovered"])
            r_rate = (rec / ops) if ops > 0 else 0.0
            p_rate = (rec / att) if att > 0 else 0.0

            results.append(SegmentMetrics(
                segment_type=s_type,
                segment_value=s_val,
                total_opportunities=ops,
                revenue_at_risk=round(data["rev_at_risk"], 2),
                interventions_attempted=att,
                successful_recoveries=rec,
                recovered_revenue=round(data["rec_rev"], 2),
                recovery_rate=round(r_rate, 4),
                intervention_precision=round(p_rate, 4)
            ))

        return results
