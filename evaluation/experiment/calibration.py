"""
Calibration and Reliability Evaluation Engine for REVIVE Phase 7.
Measures Brier Score, Expected Calibration Error (ECE), and 10-bin Reliability Distributions in pure Python.
"""

from typing import List
from evaluation.experiment.models import CalibrationMetrics, ReliabilityBin


class CalibrationEvaluator:
    """Evaluates predicted recoverability probability against observed synthetic binary outcomes in pure Python."""

    @staticmethod
    def evaluate(
        predictions: List[float],
        outcomes: List[int],
        num_bins: int = 10
    ) -> CalibrationMetrics:
        """
        Calculates Brier score, ECE, MCE, and 10 reliability bins.
        predictions: List of float in [0.0, 1.0]
        outcomes: List of binary outcomes {0, 1}
        """
        if not predictions or len(predictions) != len(outcomes):
            return CalibrationMetrics(
                brier_score=0.0,
                expected_calibration_error=0.0,
                maximum_calibration_error=0.0,
                reliability_bins=[]
            )

        n = len(predictions)

        # Brier Score
        squared_errors = [(p - y) ** 2 for p, y in zip(predictions, outcomes)]
        brier = sum(squared_errors) / n

        # 10 Reliability Bins
        bins: List[ReliabilityBin] = []
        bin_width = 1.0 / num_bins
        ece = 0.0
        mce = 0.0

        for i in range(num_bins):
            low = i * bin_width
            high = (i + 1) * bin_width

            bin_preds = []
            bin_outs = []
            for p, y in zip(predictions, outcomes):
                if i == num_bins - 1:
                    in_bin = (low <= p <= high)
                else:
                    in_bin = (low <= p < high)
                if in_bin:
                    bin_preds.append(p)
                    bin_outs.append(y)

            count = len(bin_preds)
            if count > 0:
                avg_pred = sum(bin_preds) / count
                obs_rate = sum(bin_outs) / count
                err = abs(avg_pred - obs_rate)
            else:
                avg_pred = (low + high) / 2.0
                obs_rate = 0.0
                err = 0.0

            ece += (count / n) * err
            if count > 0 and err > mce:
                mce = err

            bins.append(ReliabilityBin(
                bin_index=i + 1,
                bin_range=f"[{low:.1f}, {high:.1f}{']' if i == num_bins - 1 else ')'}",
                sample_count=count,
                avg_predicted_prob=round(avg_pred, 4),
                observed_recovery_rate=round(obs_rate, 4),
                calibration_error=round(err, 4)
            ))

        return CalibrationMetrics(
            brier_score=round(brier, 4),
            expected_calibration_error=round(ece, 4),
            maximum_calibration_error=round(mce, 4),
            reliability_bins=bins
        )
