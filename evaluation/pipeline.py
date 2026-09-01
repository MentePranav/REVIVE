"""
Evaluation Pipeline orchestrator for REVIVE.
Executes strategies in strict chronological order without look-ahead or ground-truth leakage.
"""

import csv
import datetime
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from evaluation.guards import LifecycleGuard
from evaluation.metrics import MetricsCalculator
from evaluation.models import (
    ActionCostConfig,
    BenchmarkComparison,
    EvaluationMetrics,
    EvaluationOutcomeRecord,
    StrategyDecision,
)
from evaluation.outcome_evaluator import OutcomeEvaluator
from evaluation.strategy_interface import BaseStrategy
from simulator.enums import PaymentStatus
from simulator.ground_truth_schema import GroundTruthRecord
from simulator.public_schema import AbandonedCheckout, Customer, Transaction


class DatasetLoader:
    """Loads and indexes synthetic dataset collections."""

    @classmethod
    def load(cls, data_dir: Path | str) -> Tuple[
        Dict[str, Customer],
        List[Transaction],
        List[AbandonedCheckout],
        Dict[str, GroundTruthRecord]
    ]:
        path = Path(data_dir)
        cust_file = path / "customers.jsonl"
        txn_file = path / "transactions.jsonl"
        chk_file = path / "abandoned_checkouts.jsonl"
        gt_file = path / "ground_truth.jsonl"

        if not (cust_file.exists() and txn_file.exists() and chk_file.exists() and gt_file.exists()):
            raise FileNotFoundError(f"Dataset directory {path} is missing required .jsonl files.")

        customers_by_id: Dict[str, Customer] = {}
        with open(cust_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    c = Customer.model_validate_json(line)
                    customers_by_id[c.customer_id] = c

        transactions: List[Transaction] = []
        with open(txn_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    t = Transaction.model_validate_json(line)
                    transactions.append(t)

        checkouts: List[AbandonedCheckout] = []
        with open(chk_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chk = AbandonedCheckout.model_validate_json(line)
                    checkouts.append(chk)

        ground_truth_map: Dict[str, GroundTruthRecord] = {}
        with open(gt_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    gt = GroundTruthRecord.model_validate_json(line)
                    ground_truth_map[gt.event_id] = gt

        return customers_by_id, transactions, checkouts, ground_truth_map


class EvaluationPipeline:
    """End-to-end benchmarking harness."""

    def __init__(self, cost_config: Optional[ActionCostConfig] = None):
        self.evaluator = OutcomeEvaluator(cost_config)

    def evaluate_strategy(
        self,
        strategy: BaseStrategy,
        data_dir: Path | str,
        natural_recovery_rev: float = 0.0
    ) -> Tuple[EvaluationMetrics, List[EvaluationOutcomeRecord]]:
        customers_by_id, transactions, checkouts, ground_truth_map = DatasetLoader.load(data_dir)

        # 1. Filter eligible failure events (Failed transactions + Abandoned checkouts)
        failed_txns = [t for t in transactions if t.status == PaymentStatus.FAILED]
        all_events: List[Union[Transaction, AbandonedCheckout]] = []
        all_events.extend(failed_txns)
        all_events.extend(checkouts)

        # 2. Sort all events strictly by chronological timestamp (No Look-Ahead Guarantee)
        all_events.sort(key=lambda e: e.created_at)

        outcome_records: List[EvaluationOutcomeRecord] = []
        event_actions_history: Dict[str, List[StrategyDecision]] = {}

        # 3. Step-by-step chronological execution
        for event in all_events:
            event_id = event.transaction_id if isinstance(event, Transaction) else event.checkout_id
            customer = customers_by_id.get(event.customer_id)
            prior_actions = event_actions_history.get(event_id, [])

            # Check lifecycle guard
            is_eligible, guard_reason = LifecycleGuard.is_eligible_for_intervention(event, prior_actions)

            # Strategy decision
            decision = strategy.decide(event, customer, prior_actions)
            decision.eligible = is_eligible

            # Track action history
            event_actions_history.setdefault(event_id, []).append(decision)

            # Evaluate outcome against ground truth
            gt = ground_truth_map.get(event_id)
            outcome_record = self.evaluator.evaluate_decision(decision, event, gt)
            outcome_records.append(outcome_record)

        # 4. Compute aggregated metrics
        all_gt_list = list(ground_truth_map.values())
        metrics = MetricsCalculator.calculate(
            strategy_name=strategy.name,
            records=outcome_records,
            ground_truth_records=all_gt_list,
            total_txns=len(transactions),
            failed_txns=len(failed_txns),
            abandoned_checkouts=len(checkouts),
            natural_recovery_revenue=natural_recovery_rev
        )

        return metrics, outcome_records

    def run_benchmark_comparison(
        self,
        strategies: List[BaseStrategy],
        data_dir: Path | str,
        output_dir: Optional[Path | str] = None
    ) -> BenchmarkComparison:
        """Runs full comparative benchmark across multiple strategies."""
        path = Path(data_dir)
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Step 1: Run NO_ACTION first to establish baseline natural recovery
        no_action_strat = next((s for s in strategies if s.name == "NO_ACTION"), None)
        if no_action_strat:
            no_action_metrics, _ = self.evaluate_strategy(no_action_strat, path, natural_recovery_rev=0.0)
            natural_recovery_rev = no_action_metrics.recovered_revenue
        else:
            natural_recovery_rev = 0.0

        strategy_metrics_map: Dict[str, EvaluationMetrics] = {}

        for strat in strategies:
            metrics, records = self.evaluate_strategy(
                strategy=strat,
                data_dir=path,
                natural_recovery_rev=natural_recovery_rev
            )
            strategy_metrics_map[strat.name] = metrics

            # Write decision log if output directory is provided
            if output_dir:
                out_path = Path(output_dir)
                out_path.mkdir(parents=True, exist_ok=True)
                log_file = out_path / f"decisions_{strat.name.lower()}.jsonl"
                with open(log_file, "w", encoding="utf-8") as f:
                    for rec in records:
                        f.write(rec.model_dump_json() + "\n")

        comparison = BenchmarkComparison(
            dataset_path=str(path.resolve()),
            evaluated_at=timestamp_str,
            strategy_metrics=strategy_metrics_map
        )

        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            summary_file = out_path / "benchmark_summary.json"
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(comparison.model_dump_json(indent=2))

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

        return comparison
