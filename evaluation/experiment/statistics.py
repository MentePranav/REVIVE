"""
Statistical and Bootstrap Analysis Engine for REVIVE Experimental Evaluation.
Provides multi-seed aggregation and deterministic non-parametric bootstrap confidence intervals in pure Python.
"""

import math
import random
import statistics
from typing import List

from evaluation.experiment.models import BootstrapResult, StatisticalSummary


class StatisticsEngine:
    """Computes descriptive statistics and non-parametric bootstrap confidence intervals in pure Python."""

    @staticmethod
    def calculate_summary(values: List[float]) -> StatisticalSummary:
        """Calculates mean, standard deviation, median, min, and max across a list of metrics."""
        if not values:
            return StatisticalSummary(mean=0.0, std=0.0, median=0.0, min_val=0.0, max_val=0.0)

        mean_val = float(statistics.mean(values))
        std_val = float(statistics.stdev(values)) if len(values) > 1 else 0.0
        med_val = float(statistics.median(values))
        min_v = float(min(values))
        max_v = float(max(values))

        return StatisticalSummary(
            mean=round(mean_val, 4),
            std=round(std_val, 4),
            median=round(med_val, 4),
            min_val=round(min_v, 4),
            max_val=round(max_v, 4)
        )

    @staticmethod
    def bootstrap_ci(
        data: List[float],
        n_bootstrap: int = 1000,
        confidence_level: float = 0.95,
        seed: int = 42,
        metric_name: str = "metric"
    ) -> BootstrapResult:
        """
        Computes non-parametric bootstrap confidence intervals for the sample mean.
        Guarantees deterministic reproducibility through a fixed PRNG seed.
        """
        if not data:
            return BootstrapResult(
                metric_name=metric_name,
                point_estimate=0.0,
                ci_lower=0.0,
                ci_upper=0.0,
                confidence_level=confidence_level,
                resamples=n_bootstrap
            )

        rng = random.Random(seed)
        n = len(data)
        point_estimate = float(statistics.mean(data))

        # Perform resamples
        boot_means: List[float] = []
        for _ in range(n_bootstrap):
            sample = [rng.choice(data) for _ in range(n)]
            boot_means.append(statistics.mean(sample))

        boot_means.sort()

        alpha = 1.0 - confidence_level
        lower_idx = int(math.floor((alpha / 2.0) * n_bootstrap))
        upper_idx = int(math.ceil((1.0 - alpha / 2.0) * n_bootstrap)) - 1
        lower_idx = max(0, min(lower_idx, n_bootstrap - 1))
        upper_idx = max(0, min(upper_idx, n_bootstrap - 1))

        ci_lower = float(boot_means[lower_idx])
        ci_upper = float(boot_means[upper_idx])

        return BootstrapResult(
            metric_name=metric_name,
            point_estimate=round(point_estimate, 4),
            ci_lower=round(ci_lower, 4),
            ci_upper=round(ci_upper, 4),
            confidence_level=confidence_level,
            resamples=n_bootstrap
        )
