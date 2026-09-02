"""
REVIVE — Experimental Evaluation & Holdout Benchmarking Framework.
"""

from evaluation.experiment.calibration import CalibrationEvaluator
from evaluation.experiment.claim_guardrails import ClaimGuardrails
from evaluation.experiment.config import ExperimentConfig
from evaluation.experiment.dataset_splitter import DatasetBundle, DatasetSplitter
from evaluation.experiment.failure_analysis import FailureAnalyzer
from evaluation.experiment.models import (
    AccountingReconciliation,
    BootstrapResult,
    CalibrationMetrics,
    FailureAnalysisReport,
    MultiSeedAggregateReport,
    ReliabilityBin,
    SeedExperimentResult,
    SegmentMetrics,
    StatisticalSummary,
)
from evaluation.experiment.reporter import BenchmarkReporter
from evaluation.experiment.runner import ExperimentRunner
from evaluation.experiment.segment_analysis import SegmentAnalyzer
from evaluation.experiment.statistics import StatisticsEngine

__version__ = "1.0.0"
__all__ = [
    "ExperimentConfig",
    "DatasetSplitter",
    "DatasetBundle",
    "StatisticsEngine",
    "CalibrationEvaluator",
    "SegmentAnalyzer",
    "FailureAnalyzer",
    "ClaimGuardrails",
    "BenchmarkReporter",
    "ExperimentRunner",
    "StatisticalSummary",
    "BootstrapResult",
    "CalibrationMetrics",
    "ReliabilityBin",
    "SegmentMetrics",
    "FailureAnalysisReport",
    "AccountingReconciliation",
    "SeedExperimentResult",
    "MultiSeedAggregateReport",
]
