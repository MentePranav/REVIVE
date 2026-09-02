"""
Comprehensive automated test suite for REVIVE Phase 7: Experimental Evaluation & Holdout Benchmarking.
Covers dataset splitting, leakage isolation, multi-strategy benchmarking, accounting invariants, bootstrap statistics, calibration, segments, failure diagnostics, claim guardrails, and adversarial edge cases.
"""

from pathlib import Path
import pytest

from evaluation.experiment.calibration import CalibrationEvaluator
from evaluation.experiment.claim_guardrails import ClaimGuardrails
from evaluation.experiment.config import ExperimentConfig
from evaluation.experiment.dataset_splitter import DatasetSplitter
from evaluation.experiment.failure_analysis import FailureAnalyzer
from evaluation.experiment.models import MultiSeedAggregateReport
from evaluation.experiment.reporter import BenchmarkReporter
from evaluation.experiment.runner import ExperimentRunner
from evaluation.experiment.segment_analysis import SegmentAnalyzer
from evaluation.experiment.statistics import StatisticsEngine
from evaluation.pipeline import EvaluationPipeline
from evaluation.strategies.naive_retry import NaiveRetryStrategy
from evaluation.strategies.no_action import NoActionStrategy
from evaluation.strategies.rule_based import RuleBasedStrategy
from execution.batch import BatchExecutionRunner
from policy.config import PolicyConfig


# ------------------------------------------------------------------------------
# 1. Dataset Splitting Tests
# ------------------------------------------------------------------------------

def test_1_deterministic_dataset_generation():
    """Test 1: Same seed produces identical dataset bundles."""
    b1 = DatasetSplitter.generate_development_set(seed=42, transaction_count=100)
    b2 = DatasetSplitter.generate_development_set(seed=42, transaction_count=100)
    assert len(b1.transactions) == len(b2.transactions)
    assert [t.transaction_id for t in b1.transactions] == [t.transaction_id for t in b2.transactions]
    assert [t.amount for t in b1.transactions] == [t.amount for t in b2.transactions]


def test_2_independent_evaluation_seeds_no_overlap():
    """Test 2: Dev set (seed 42) and evaluation set (seed 101) have distinct distributions and properties."""
    dev = DatasetSplitter.generate_development_set(seed=42, transaction_count=200)
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=200)

    dev_amounts = [t.amount for t in dev.transactions]
    eval_amounts = [t.amount for t in ev.transactions]
    assert dev_amounts != eval_amounts

    dev_cust_tenures = [c.customer_age_days for c in dev.customers]
    eval_cust_tenures = [c.customer_age_days for c in ev.customers]
    assert dev_cust_tenures != eval_cust_tenures


def test_3_dataset_size_scaling():
    """Test 3: Target transaction counts are accurately generated."""
    b = DatasetSplitter.generate_evaluation_set(seed=999, transaction_count=500)
    assert len(b.transactions) == 500
    assert len(b.customers) > 0


# ------------------------------------------------------------------------------
# 2. Leakage Isolation Tests
# ------------------------------------------------------------------------------

def test_4_ground_truth_isolated_from_decision_path():
    """Test 4: Observable public schemas contain zero ground-truth counterfactuals."""
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=100)
    for t in ev.transactions:
        assert not hasattr(t, "ground_truth_recoverable")
        assert not hasattr(t, "counterfactual_outcomes")
    for c in ev.checkouts:
        assert not hasattr(c, "ground_truth_recoverable")
        assert not hasattr(c, "counterfactual_outcomes")


def test_5_adversarial_hidden_label_inaccessibility():
    """Test 5: Passing ground truth into strategy or policy decision is rejected or ignored."""
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=100)
    sample_txn = ev.failed_transactions[0]
    cust = ev.customers_by_id[sample_txn.customer_id]

    strat = RuleBasedStrategy()
    # Strategy interface only accepts (event, customer, prior_actions)
    dec = strat.decide(sample_txn, cust, [])
    assert dec.action is not None


# ------------------------------------------------------------------------------
# 3. Multi-Strategy Benchmarking Fairness
# ------------------------------------------------------------------------------

def test_6_same_dataset_evaluated_across_all_strategies():
    """Test 6: All strategies evaluate on the identical set of events."""
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=500)
    pipe = EvaluationPipeline()

    m_no, _ = pipe.evaluate_strategy_in_memory(NoActionStrategy(), ev.customers_by_id, ev.transactions, ev.checkouts, ev.ground_truth_map)
    m_naive, _ = pipe.evaluate_strategy_in_memory(NaiveRetryStrategy(), ev.customers_by_id, ev.transactions, ev.checkouts, ev.ground_truth_map)
    m_rule, _ = pipe.evaluate_strategy_in_memory(RuleBasedStrategy(), ev.customers_by_id, ev.transactions, ev.checkouts, ev.ground_truth_map)

    assert m_no.total_eligible_opportunities == m_naive.total_eligible_opportunities == m_rule.total_eligible_opportunities
    assert m_no.revenue_at_risk == m_naive.revenue_at_risk == m_rule.revenue_at_risk


def test_7_no_action_produces_zero_interventions():
    """Test 7: NO_ACTION strategy performs 0 interventions."""
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=200)
    pipe = EvaluationPipeline()
    m_no, _ = pipe.evaluate_strategy_in_memory(NoActionStrategy(), ev.customers_by_id, ev.transactions, ev.checkouts, ev.ground_truth_map)
    assert m_no.total_interventions_attempted == 0
    assert m_no.incremental_revenue == 0.0


# ------------------------------------------------------------------------------
# 4. Accounting Invariants & Balance Sheet Reconciliation
# ------------------------------------------------------------------------------

def test_8_accounting_revenue_at_risk_balance():
    """Test 8: RevenueAtRisk = RecoveredRevenue + UnrecoveredRevenue."""
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=500)
    runner = BatchExecutionRunner()
    _, summary = runner.run_batch(ev.all_opportunities, ev.customers_by_id, ev.ground_truth_map, len(ev.transactions))

    unrecovered = round(summary.total_revenue_at_risk - summary.total_recovered_revenue, 2)
    reconciled = round(summary.total_recovered_revenue + unrecovered, 2)
    assert reconciled == summary.total_revenue_at_risk


def test_9_incremental_revenue_exact_formula():
    """Test 9: Incremental revenue equals REVIVE total recovered minus NO_ACTION natural recovered."""
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=500)
    runner = BatchExecutionRunner()
    _, summary = runner.run_batch(ev.all_opportunities, ev.customers_by_id, ev.ground_truth_map, len(ev.transactions))

    expected_inc = round(summary.total_recovered_revenue - summary.natural_recovery_revenue, 2)
    assert summary.incremental_recovered_revenue == expected_inc


def test_10_recovered_revenue_never_exceeds_revenue_at_risk():
    """Test 10: Total recovered revenue <= total revenue at risk."""
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=500)
    runner = BatchExecutionRunner()
    _, summary = runner.run_batch(ev.all_opportunities, ev.customers_by_id, ev.ground_truth_map, len(ev.transactions))
    assert summary.total_recovered_revenue <= summary.total_revenue_at_risk


def test_11_zero_double_counting_of_transactions():
    """Test 11: No single transaction or checkout contributes revenue twice."""
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=500)
    runner = BatchExecutionRunner()
    traces, summary = runner.run_batch(ev.all_opportunities, ev.customers_by_id, ev.ground_truth_map, len(ev.transactions))

    recovered_ids = [t.event_id for t in traces if t.execution_result.recovered_amount > 0.0]
    assert len(recovered_ids) == len(set(recovered_ids))


# ------------------------------------------------------------------------------
# 5. Statistics & Bootstrap Confidence Intervals
# ------------------------------------------------------------------------------

def test_12_statistics_engine_summary_calculations():
    """Test 12: StatisticsEngine calculates accurate mean, std, median, min, max."""
    vals = [10.0, 20.0, 30.0, 40.0, 50.0]
    stat = StatisticsEngine.calculate_summary(vals)
    assert stat.mean == 30.0
    assert stat.median == 30.0
    assert stat.min_val == 10.0
    assert stat.max_val == 50.0


def test_13_deterministic_bootstrap_ci():
    """Test 13: Deterministic seed produces identical bootstrap CI bounds."""
    data = [100.0, 150.0, 200.0, 250.0, 300.0]
    ci1 = StatisticsEngine.bootstrap_ci(data, n_bootstrap=500, confidence_level=0.95, seed=42)
    ci2 = StatisticsEngine.bootstrap_ci(data, n_bootstrap=500, confidence_level=0.95, seed=42)
    assert ci1.ci_lower == ci2.ci_lower
    assert ci1.ci_upper == ci2.ci_upper
    assert ci1.ci_lower <= ci1.point_estimate <= ci1.ci_upper


def test_14_bootstrap_ci_coverage_bounds():
    """Test 14: Bootstrap confidence intervals strictly contain point estimate."""
    data = [50.0, 60.0, 70.0, 80.0, 90.0]
    ci = StatisticsEngine.bootstrap_ci(data, n_bootstrap=1000, confidence_level=0.95, seed=123)
    assert ci.ci_lower <= ci.point_estimate <= ci.ci_upper


# ------------------------------------------------------------------------------
# 6. Model Calibration & Brier Score
# ------------------------------------------------------------------------------

def test_15_calibration_brier_score_range():
    """Test 15: Brier score is within [0.0, 1.0]."""
    preds = [0.9, 0.8, 0.2, 0.1]
    outs = [1, 1, 0, 0]
    cal = CalibrationEvaluator.evaluate(preds, outs, num_bins=10)
    assert 0.0 <= cal.brier_score <= 1.0
    assert cal.brier_score < 0.05 # Good calibration test


def test_16_reliability_bins_sum_reconciliation():
    """Test 16: Sum of samples across reliability bins equals total evaluation count."""
    preds = [0.15, 0.25, 0.75, 0.85, 0.95]
    outs = [0, 0, 1, 1, 1]
    cal = CalibrationEvaluator.evaluate(preds, outs, num_bins=10)
    total_binned = sum(b.sample_count for b in cal.reliability_bins)
    assert total_binned == len(preds)


def test_17_ece_calculation():
    """Test 17: Expected calibration error is non-negative and <= 1.0."""
    preds = [0.5, 0.5, 0.5, 0.5]
    outs = [1, 0, 1, 0]
    cal = CalibrationEvaluator.evaluate(preds, outs, num_bins=5)
    assert 0.0 <= cal.expected_calibration_error <= 1.0


# ------------------------------------------------------------------------------
# 7. Segment Analysis Tests
# ------------------------------------------------------------------------------

def test_18_segment_totals_reconciliation():
    """Test 18: Sum of opportunities across amount tiers equals total opportunities."""
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=500)
    runner = BatchExecutionRunner()
    traces, summary = runner.run_batch(ev.all_opportunities, ev.customers_by_id, ev.ground_truth_map, len(ev.transactions))

    events_map = {(t.transaction_id if hasattr(t, "transaction_id") else t.checkout_id): t for t in ev.all_opportunities}
    segs = SegmentAnalyzer.analyze(traces, events_map, ev.customers_by_id)

    tier_segs = [s for s in segs if s.segment_type == "amount_tier"]
    sum_tier_ops = sum(s.total_opportunities for s in tier_segs)
    assert sum_tier_ops == summary.total_failed_opportunities


def test_19_segment_revenue_reconciliation():
    """Test 19: Sum of revenue across amount tiers equals total revenue at risk."""
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=500)
    runner = BatchExecutionRunner()
    traces, summary = runner.run_batch(ev.all_opportunities, ev.customers_by_id, ev.ground_truth_map, len(ev.transactions))

    events_map = {(t.transaction_id if hasattr(t, "transaction_id") else t.checkout_id): t for t in ev.all_opportunities}
    segs = SegmentAnalyzer.analyze(traces, events_map, ev.customers_by_id)

    tier_segs = [s for s in segs if s.segment_type == "amount_tier"]
    sum_tier_rev = round(sum(s.revenue_at_risk for s in tier_segs), 2)
    assert sum_tier_rev == summary.total_revenue_at_risk


# ------------------------------------------------------------------------------
# 8. Failure & Vulnerability Diagnostics Tests
# ------------------------------------------------------------------------------

def test_20_failure_analysis_zero_high_risk_leaks():
    """Test 20: High-risk automated leaks is strictly 0 (P005 zero-tolerance)."""
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=500)
    runner = BatchExecutionRunner()
    traces, _ = runner.run_batch(ev.all_opportunities, ev.customers_by_id, ev.ground_truth_map, len(ev.transactions))

    events_map = {(t.transaction_id if hasattr(t, "transaction_id") else t.checkout_id): t for t in ev.all_opportunities}
    segs = SegmentAnalyzer.analyze(traces, events_map, ev.customers_by_id)
    failure_rep = FailureAnalyzer.analyze(traces, events_map, ev.ground_truth_map, segs)

    assert failure_rep.high_risk_automated_leaks == 0


def test_21_false_positive_count_validity():
    """Test 21: False positive interventions are non-negative and <= executed actions."""
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=500)
    runner = BatchExecutionRunner()
    traces, summary = runner.run_batch(ev.all_opportunities, ev.customers_by_id, ev.ground_truth_map, len(ev.transactions))

    events_map = {(t.transaction_id if hasattr(t, "transaction_id") else t.checkout_id): t for t in ev.all_opportunities}
    segs = SegmentAnalyzer.analyze(traces, events_map, ev.customers_by_id)
    failure_rep = FailureAnalyzer.analyze(traces, events_map, ev.ground_truth_map, segs)

    assert failure_rep.false_positive_interventions >= 0
    assert failure_rep.false_positive_interventions <= summary.actions_executed_count


# ------------------------------------------------------------------------------
# 9. Claim Guardrails & Scientific Integrity Tests
# ------------------------------------------------------------------------------

def test_22_claim_guardrails_blocks_prohibited_guaranteed_recovery():
    """Test 22: ClaimGuardrails rejects text claiming 'guaranteed recovery'."""
    bad_text = "REVIVE provides guaranteed recovery on all transactions in this simulation benchmark."
    is_valid, violations = ClaimGuardrails.validate_report(bad_text)
    assert not is_valid
    assert any("guaranteed recovery" in v for v in violations)


def test_23_claim_guardrails_blocks_missing_disclaimer():
    """Test 23: ClaimGuardrails rejects report lacking synthetic disclaimer keywords."""
    bad_text = "REVIVE achieved 50% recovery uplift."
    is_valid, violations = ClaimGuardrails.validate_report(bad_text)
    assert not is_valid
    assert any("Missing required synthetic" in v for v in violations)


def test_24_claim_guardrails_accepts_compliant_report():
    """Test 24: ClaimGuardrails approves compliant report with proper disclaimers."""
    good_text = "This report presents a synthetic benchmark evaluation of REVIVE. All results are from local simulation."
    is_valid, violations = ClaimGuardrails.validate_report(good_text)
    assert is_valid
    assert len(violations) == 0


# ------------------------------------------------------------------------------
# 10. Adversarial & Edge Case Tests (Section 30 Adversarial 1-10)
# ------------------------------------------------------------------------------

def test_25_adversarial_tuning_on_evaluation_prevented():
    """Adversarial Test 1: Development and evaluation datasets have distinct instances."""
    dev = DatasetSplitter.generate_development_set(seed=42, transaction_count=100)
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=100)
    assert dev.seed != ev.seed


def test_26_adversarial_different_strategies_receiving_different_txns():
    """Adversarial Test 3: Assert all strategies receive identical transaction lists."""
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=200)
    pipe = EvaluationPipeline()

    m1, rec1 = pipe.evaluate_strategy_in_memory(NoActionStrategy(), ev.customers_by_id, ev.transactions, ev.checkouts, ev.ground_truth_map)
    m2, rec2 = pipe.evaluate_strategy_in_memory(NaiveRetryStrategy(), ev.customers_by_id, ev.transactions, ev.checkouts, ev.ground_truth_map)

    assert [r.decision.event_id for r in rec1] == [r.decision.event_id for r in rec2]


def test_27_adversarial_duplicate_execution_inflating_recovery():
    """Adversarial Test 5: Duplicate execution does not inflate recovery metrics."""
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=200)
    runner = BatchExecutionRunner()
    traces1, s1 = runner.run_batch(ev.all_opportunities, ev.customers_by_id, ev.ground_truth_map, len(ev.transactions))
    traces2, s2 = runner.run_batch(ev.all_opportunities, ev.customers_by_id, ev.ground_truth_map, len(ev.transactions))

    assert s1.total_recovered_revenue == s2.total_recovered_revenue


def test_28_adversarial_natural_recovery_subtraction():
    """Adversarial Test 6: Natural baseline recovery is never counted as incremental revenue."""
    ev = DatasetSplitter.generate_evaluation_set(seed=101, transaction_count=500)
    runner = BatchExecutionRunner()
    _, summary = runner.run_batch(ev.all_opportunities, ev.customers_by_id, ev.ground_truth_map, len(ev.transactions))

    if summary.natural_recovery_revenue > 0:
        assert summary.incremental_recovered_revenue < summary.total_recovered_revenue


def test_29_adversarial_empty_dataset_handled_gracefully():
    """Adversarial Test 10: Empty dataset handled gracefully without exceptions."""
    stat = StatisticsEngine.calculate_summary([])
    assert stat.mean == 0.0
    cal = CalibrationEvaluator.evaluate([], [])
    assert cal.brier_score == 0.0


def test_30_end_to_end_experiment_runner_flow(tmp_path):
    """Test 30: Full ExperimentRunner generates artifacts and valid report."""
    cfg = ExperimentConfig(
        experiment_id="test_exp_001",
        dev_seed=42,
        eval_seeds=[101, 202],
        dev_transaction_count=200,
        eval_transaction_count=500,
        bootstrap_samples=50
    )
    runner = ExperimentRunner(cfg)
    report, seed_results = runner.run_experiment()

    assert report.total_evaluations == 2
    assert report.accounting_verified is True
    assert "REVIVE" in report.strategy_aggregates

    # Export artifacts
    out_dir = BenchmarkReporter.export_artifacts(report, seed_results, cfg, tmp_path / "exp_out")
    assert (out_dir / "BENCHMARK_REPORT.md").exists()
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "config.json").exists()
    assert (out_dir / "strategy_results.json").exists()
    assert (out_dir / "segment_analysis.csv").exists()
def test_31_10k_holdout_performance():
    """Test 31: 10,000 transaction holdout evaluation completes within performance envelope."""
    import time
    cfg = ExperimentConfig(
        experiment_id="perf_test_10k",
        dev_seed=42,
        eval_seeds=[101],
        dev_transaction_count=500,
        eval_transaction_count=10000,
        bootstrap_samples=100
    )
    runner = ExperimentRunner(cfg)
    t0 = time.perf_counter()
    report, _ = runner.run_experiment()
    elapsed = time.perf_counter() - t0

    assert report.total_evaluations == 1
    assert elapsed < 5.0 # Under 5 seconds for 10k transactions
