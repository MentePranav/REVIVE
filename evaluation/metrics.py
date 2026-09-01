"""
Metrics calculation engine for the REVIVE benchmark suite.
Computes objective financial and operational recovery metrics.
"""

from typing import List, Dict
from evaluation.models import EvaluationMetrics, EvaluationOutcomeRecord
from simulator.enums import RecoveryAction
from simulator.ground_truth_schema import GroundTruthRecord


class MetricsCalculator:
    """Computes comprehensive benchmark metrics for an evaluated strategy."""

    @classmethod
    def calculate(
        cls,
        strategy_name: str,
        records: List[EvaluationOutcomeRecord],
        ground_truth_records: List[GroundTruthRecord],
        total_txns: int,
        failed_txns: int,
        abandoned_checkouts: int,
        natural_recovery_revenue: float = 0.0
    ) -> EvaluationMetrics:
        # Active interventions (excluding passive DO_NOTHING)
        active_records = [r for r in records if r.decision.action != RecoveryAction.DO_NOTHING]
        total_interventions = len(active_records)

        # Successful active recoveries
        successful_active = [r for r in active_records if r.is_recovered and r.recovered_amount > 0.0]
        successful_count = len(successful_active)

        # Total revenue recovered by strategy
        total_recovered_rev = sum(r.recovered_amount for r in records)

        # Revenue at risk
        rev_at_risk = sum(r.amount for r in records)

        # Incremental revenue relative to NO_ACTION
        incremental_rev = max(0.0, total_recovered_rev - natural_recovery_revenue)

        # Intervention Precision
        precision = (successful_count / total_interventions) if total_interventions > 0 else 0.0

        # Total true recoverable opportunities in ground truth
        total_true_recoverable_ops = sum(1 for gt in ground_truth_records if gt.ground_truth_recoverable)
        # Capture Rate
        all_recovered_count = sum(1 for r in records if r.is_recovered)
        capture_rate = (all_recovered_count / total_true_recoverable_ops) if total_true_recoverable_ops > 0 else 0.0

        # False positive rate (active interventions that failed or were redundant)
        false_positive_count = sum(1 for r in active_records if r.is_false_positive)
        fp_rate = (false_positive_count / total_interventions) if total_interventions > 0 else 0.0

        # Action costs & Net Incremental Value
        total_costs = sum(r.action_cost for r in records)
        net_value = incremental_rev - total_costs

        return EvaluationMetrics(
            strategy_name=strategy_name,
            total_transactions_evaluated=total_txns,
            failed_transactions_considered=failed_txns,
            abandoned_checkouts_considered=abandoned_checkouts,
            total_eligible_opportunities=len(records),
            total_interventions_attempted=total_interventions,
            successful_recoveries=successful_count,
            recovered_revenue=round(total_recovered_rev, 2),
            revenue_at_risk=round(rev_at_risk, 2),
            natural_recovery_revenue=round(natural_recovery_revenue, 2),
            incremental_revenue=round(incremental_rev, 2),
            intervention_precision=round(precision, 4),
            recoverable_opportunity_capture_rate=round(capture_rate, 4),
            false_positive_rate=round(fp_rate, 4),
            total_action_costs=round(total_costs, 2),
            net_incremental_value=round(net_value, 2)
        )
