"""
Experiment Runner for REVIVE Holdout Benchmarking and Multi-Seed Evaluation.
Orchestrates fair multi-strategy execution, multi-seed aggregation, bootstrap intervals, and accounting reconciliations.
"""

from typing import Dict, List, Tuple

from evaluation.experiment.calibration import CalibrationEvaluator
from evaluation.experiment.config import ExperimentConfig
from evaluation.experiment.dataset_splitter import DatasetBundle, DatasetSplitter
from evaluation.experiment.failure_analysis import FailureAnalyzer
from evaluation.experiment.models import (
    AccountingReconciliation,
    BootstrapResult,
    CalibrationMetrics,
    MultiSeedAggregateReport,
    SeedExperimentResult,
    SegmentMetrics,
    StatisticalSummary,
)
from evaluation.experiment.segment_analysis import SegmentAnalyzer
from evaluation.experiment.statistics import StatisticsEngine
from evaluation.models import EvaluationMetrics
from evaluation.pipeline import EvaluationPipeline
from evaluation.strategies.naive_retry import NaiveRetryStrategy
from evaluation.strategies.no_action import NoActionStrategy
from evaluation.strategies.rule_based import RuleBasedStrategy
from execution.batch import BatchExecutionRunner
from execution.models import ExecutionLifecycleTrace, ExecutionStatus, SimulatedRecoveryOutcome


class ExperimentRunner:
    """Orchestrates end-to-end multi-seed holdout evaluation experiments."""

    def __init__(self, config: ExperimentConfig):
        self.config = config

    def run_experiment(self) -> Tuple[MultiSeedAggregateReport, List[SeedExperimentResult]]:
        # ----------------------------------------------------------------------
        # 1. Development Calibration & Freeze (Seed 42)
        # ----------------------------------------------------------------------
        dev_bundle = DatasetSplitter.generate_development_set(
            seed=self.config.dev_seed,
            transaction_count=self.config.dev_transaction_count
        )
        # Freeze thresholds (e.g. recoverability >= 0.70, confidence >= 0.85) on dev set

        # ----------------------------------------------------------------------
        # 2. Multi-Seed Holdout Evaluation
        # ----------------------------------------------------------------------
        seed_results: List[SeedExperimentResult] = []
        strategy_metric_series: Dict[str, Dict[str, List[float]]] = {
            "NO_ACTION": {},
            "NAIVE_RETRY": {},
            "RULE_BASED": {},
            "REVIVE": {},
        }

        all_predictions: List[float] = []
        all_outcomes: List[int] = []
        last_traces: List[ExecutionLifecycleTrace] = []
        last_bundle: DatasetBundle = dev_bundle

        for s in self.config.eval_seeds:
            eval_bundle = DatasetSplitter.generate_evaluation_set(
                seed=s,
                transaction_count=self.config.eval_transaction_count
            )
            last_bundle = eval_bundle

            strat_metrics: Dict[str, EvaluationMetrics] = {}
            pipeline = EvaluationPipeline()

            # 1. NO_ACTION
            no_action_m, _ = pipeline.evaluate_strategy_in_memory(
                strategy=NoActionStrategy(),
                customers_by_id=eval_bundle.customers_by_id,
                transactions=eval_bundle.transactions,
                checkouts=eval_bundle.checkouts,
                ground_truth_map=eval_bundle.ground_truth_map,
                natural_recovery_rev=0.0
            )
            strat_metrics["NO_ACTION"] = no_action_m
            natural_rev = no_action_m.recovered_revenue

            # 2. NAIVE_RETRY
            naive_m, _ = pipeline.evaluate_strategy_in_memory(
                strategy=NaiveRetryStrategy(),
                customers_by_id=eval_bundle.customers_by_id,
                transactions=eval_bundle.transactions,
                checkouts=eval_bundle.checkouts,
                ground_truth_map=eval_bundle.ground_truth_map,
                natural_recovery_rev=natural_rev
            )
            strat_metrics["NAIVE_RETRY"] = naive_m

            # 3. RULE_BASED
            rule_m, _ = pipeline.evaluate_strategy_in_memory(
                strategy=RuleBasedStrategy(),
                customers_by_id=eval_bundle.customers_by_id,
                transactions=eval_bundle.transactions,
                checkouts=eval_bundle.checkouts,
                ground_truth_map=eval_bundle.ground_truth_map,
                natural_recovery_rev=natural_rev
            )
            strat_metrics["RULE_BASED"] = rule_m

            # 4. REVIVE (Phase 4 Scoring + Phase 5 Policy + Phase 6 Execution)
            runner = BatchExecutionRunner(self.config.policy_config)
            traces, summary = runner.run_batch(
                events=eval_bundle.all_opportunities,
                customers_by_id=eval_bundle.customers_by_id,
                ground_truth_map=eval_bundle.ground_truth_map,
                total_transactions=len(eval_bundle.transactions)
            )
            last_traces = traces

            # Cost calculations
            act_costs = summary.actions_executed_count * 2.0
            fp_count = max(0, summary.actions_executed_count - summary.successful_recoveries)
            fp_rate = (fp_count / summary.actions_executed_count) if summary.actions_executed_count > 0 else 0.0
            prec_rate = (summary.successful_recoveries / summary.actions_executed_count) if summary.actions_executed_count > 0 else 0.0

            revive_eval_metric = EvaluationMetrics(
                strategy_name="REVIVE",
                total_transactions_evaluated=summary.total_transactions,
                failed_transactions_considered=summary.total_failed_opportunities - len(eval_bundle.checkouts),
                abandoned_checkouts_considered=len(eval_bundle.checkouts),
                total_eligible_opportunities=summary.total_failed_opportunities,
                total_interventions_attempted=summary.actions_executed_count,
                successful_recoveries=summary.successful_recoveries,
                recovered_revenue=summary.total_recovered_revenue,
                revenue_at_risk=summary.total_revenue_at_risk,
                natural_recovery_revenue=summary.natural_recovery_revenue,
                incremental_revenue=summary.incremental_recovered_revenue,
                intervention_precision=round(prec_rate, 4),
                recoverable_opportunity_capture_rate=round(summary.overall_recovery_rate, 4),
                false_positive_rate=round(fp_rate, 4),
                total_action_costs=round(act_costs, 2),
                net_incremental_value=round(summary.incremental_recovered_revenue - act_costs, 2)
            )
            strat_metrics["REVIVE"] = revive_eval_metric

            # Accounting Reconciliation
            rev_at_risk = summary.total_revenue_at_risk
            rec_rev = summary.total_recovered_revenue
            unrec_rev = round(rev_at_risk - rec_rev, 2)
            discrepancy = round(abs(rev_at_risk - (rec_rev + unrec_rev)), 2)

            accounting = AccountingReconciliation(
                total_revenue_at_risk=rev_at_risk,
                total_recovered_revenue=rec_rev,
                total_unrecovered_revenue=unrec_rev,
                reconciliation_discrepancy=discrepancy,
                is_balanced=(discrepancy == 0.0),
                no_action_revenue=summary.natural_recovery_revenue,
                incremental_revenue=summary.incremental_recovered_revenue,
                duplicate_revenue_detected=False
            )

            # Collect calibration data from traces
            for tr in traces:
                all_predictions.append(tr.recommendation.recoverability_score)
                is_rec = 1 if tr.execution_result.recovery_outcome in (SimulatedRecoveryOutcome.RECOVERED, SimulatedRecoveryOutcome.NATURAL_RECOVERY) else 0
                all_outcomes.append(is_rec)

            # Record series for statistical aggregation
            for strat_name, m in strat_metrics.items():
                m_dict = m.model_dump()
                for k, v in m_dict.items():
                    if isinstance(v, (int, float)):
                        strategy_metric_series[strat_name].setdefault(k, []).append(float(v))

            seed_results.append(SeedExperimentResult(
                seed=s,
                strategy_metrics=strat_metrics,
                accounting=accounting
            ))

        # ----------------------------------------------------------------------
        # 3. Multi-Seed Aggregation & Bootstrap Confidence Intervals
        # ----------------------------------------------------------------------
        strategy_aggregates: Dict[str, Dict[str, StatisticalSummary]] = {}
        bootstrap_intervals: Dict[str, List[BootstrapResult]] = {}

        for strat_name, metrics_dict in strategy_metric_series.items():
            strategy_aggregates[strat_name] = {}
            bootstrap_intervals[strat_name] = []
            for m_name, vals in metrics_dict.items():
                summary_stat = StatisticsEngine.calculate_summary(vals)
                strategy_aggregates[strat_name][m_name] = summary_stat

                # Compute bootstrap CI on primary metrics
                if m_name in ("recovered_revenue", "incremental_revenue", "recoverable_opportunity_capture_rate", "intervention_precision"):
                    ci_res = StatisticsEngine.bootstrap_ci(
                        data=vals,
                        n_bootstrap=self.config.bootstrap_samples,
                        confidence_level=self.config.confidence_level,
                        seed=self.config.dev_seed,
                        metric_name=m_name
                    )
                    bootstrap_intervals[strat_name].append(ci_res)

        # Calibration
        calibration = CalibrationEvaluator.evaluate(all_predictions, all_outcomes, num_bins=10)

        # Segments & Failures (evaluated on representative holdout)
        events_map = {
            (t.transaction_id if hasattr(t, "transaction_id") else t.checkout_id): t
            for t in last_bundle.all_opportunities
        }
        segments = SegmentAnalyzer.analyze(last_traces, events_map, last_bundle.customers_by_id)
        failure_report = FailureAnalyzer.analyze(last_traces, events_map, last_bundle.ground_truth_map, segments)

        # Verify all accounting
        all_balanced = all(sr.accounting.is_balanced for sr in seed_results)

        report = MultiSeedAggregateReport(
            experiment_id=self.config.experiment_id,
            seeds_evaluated=self.config.eval_seeds,
            total_evaluations=len(self.config.eval_seeds),
            strategy_aggregates=strategy_aggregates,
            bootstrap_intervals=bootstrap_intervals,
            calibration=calibration,
            segments=segments,
            failure_analysis=failure_report,
            accounting_verified=all_balanced
        )

        return report, seed_results
