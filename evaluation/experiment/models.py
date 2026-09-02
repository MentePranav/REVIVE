"""
Pydantic data models for REVIVE Experimental Evaluation & Holdout Benchmarking.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from evaluation.models import EvaluationMetrics


class StatisticalSummary(BaseModel):
    """Descriptive statistics across multiple random seeds."""
    mean: float
    std: float
    median: float
    min_val: float
    max_val: float


class BootstrapResult(BaseModel):
    """Bootstrap confidence interval result for a specific performance metric."""
    metric_name: str
    point_estimate: float
    ci_lower: float
    ci_upper: float
    confidence_level: float = 0.95
    resamples: int = 1000


class ReliabilityBin(BaseModel):
    """Calibration bin comparing predicted probability to observed recovery frequency."""
    bin_index: int
    bin_range: str
    sample_count: int
    avg_predicted_prob: float
    observed_recovery_rate: float
    calibration_error: float


class CalibrationMetrics(BaseModel):
    """Model calibration evaluation metrics."""
    brier_score: float
    expected_calibration_error: float
    maximum_calibration_error: float
    reliability_bins: List[ReliabilityBin] = Field(default_factory=list)


class SegmentMetrics(BaseModel):
    """Recovery performance breakdown for a specific demographic or failure segment."""
    segment_type: str # e.g. "amount_tier", "payment_method", "failure_category"
    segment_value: str
    total_opportunities: int
    revenue_at_risk: float
    interventions_attempted: int
    successful_recoveries: int
    recovered_revenue: float
    recovery_rate: float
    intervention_precision: float


class FailureAnalysisReport(BaseModel):
    """Automated failure mode and vulnerability diagnostic report."""
    false_positive_interventions: int
    unnecessary_retries: int
    high_risk_automated_leaks: int
    low_confidence_escalations: int
    unrecovered_high_value_count: int
    unrecovered_high_value_revenue: float
    weak_segments: List[str] = Field(default_factory=list)


class AccountingReconciliation(BaseModel):
    """Strict accounting balance sheet reconciliation."""
    total_revenue_at_risk: float
    total_recovered_revenue: float
    total_unrecovered_revenue: float
    reconciliation_discrepancy: float
    is_balanced: bool
    no_action_revenue: float
    incremental_revenue: float
    duplicate_revenue_detected: bool = False


class SeedExperimentResult(BaseModel):
    """Benchmark outcome for a single evaluation seed."""
    seed: int
    strategy_metrics: Dict[str, EvaluationMetrics]
    accounting: AccountingReconciliation
    calibration: Optional[CalibrationMetrics] = None


class MultiSeedAggregateReport(BaseModel):
    """Aggregated experimental evaluation results across multiple holdout seeds."""
    experiment_id: str
    seeds_evaluated: List[int]
    total_evaluations: int
    strategy_aggregates: Dict[str, Dict[str, StatisticalSummary]]
    bootstrap_intervals: Dict[str, List[BootstrapResult]]
    calibration: CalibrationMetrics
    segments: List[SegmentMetrics]
    failure_analysis: FailureAnalysisReport
    accounting_verified: bool
    evaluation_disclaimer: str = "SYNTHETIC EVALUATION ONLY — Controlled benchmark evaluation for hackathon prototype."
