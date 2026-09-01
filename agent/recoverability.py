"""
Calibrated Recoverability Scoring Engine for REVIVE.
Computes context-aware recovery likelihoods, feature attributions, and explainability factors.
"""

import math
from typing import Dict, List, Tuple
from agent.models import (
    DiagnosisResult,
    NormalizedFailureCategory,
    RecoverabilityTier,
    ReviveFeatures,
)


class RecoverabilityScorer:
    """Computes calibrated recoverability scores and explicit feature contribution vectors."""

    @classmethod
    def score_recoverability(
        cls,
        features: ReviveFeatures,
        diagnosis: DiagnosisResult
    ) -> Tuple[float, RecoverabilityTier, Dict[str, float], List[str], List[str]]:
        cat = features.failure_category
        contributions: Dict[str, float] = {}
        pos_factors: List[str] = []
        neg_factors: List[str] = []

        # 1. Base Recoverability Prior by Category
        base_prior = cls._get_category_base_prior(features)
        contributions["base_category_prior"] = round(base_prior, 3)

        # 2. Customer Historical Track Record Contribution
        if features.historical_txns >= 3:
            # Baseline expectation is 0.70
            hist_delta = (features.historical_success_rate - 0.70) * 0.35
            contributions["historical_success_rate"] = round(hist_delta, 3)
            if hist_delta > 0.05:
                pos_factors.append(f"Strong customer track record ({features.historical_success_rate * 100:.1f}% success across {features.historical_txns} transactions)")
            elif hist_delta < -0.05:
                neg_factors.append(f"Suboptimal customer history ({features.historical_success_rate * 100:.1f}% success rate with {features.historical_failures} prior failures)")
        elif features.is_new_customer:
            new_delta = -0.08
            contributions["new_customer_uncertainty"] = new_delta
            neg_factors.append("New customer account with limited historical baseline")

        # 3. Transaction Amount vs Historical Average Anomaly
        if features.historical_txns >= 3 and features.amount_to_avg_ratio >= 3.0:
            amt_penalty = -min(0.25, 0.08 * math.log2(features.amount_to_avg_ratio))
            contributions["amount_anomaly_dampener"] = round(amt_penalty, 3)
            neg_factors.append(f"Transaction amount is {features.amount_to_avg_ratio:.1f}x higher than customer's average ticket size")
        elif features.is_subscription:
            sub_boost = 0.08
            contributions["subscription_stability"] = sub_boost
            pos_factors.append("Recurring subscription customer with stable billing tier")

        # 4. Temporal & Liquidity Adjustments (Insufficient Funds Specific)
        if cat == NormalizedFailureCategory.INSUFFICIENT_FUNDS:
            if features.is_salary_window:
                sal_boost = 0.15
                contributions["salary_window_liquidity"] = sal_boost
                pos_factors.append("Timing aligns with early-month salary liquidity cycle")
            elif features.is_month_end_shortage_window:
                me_penalty = -0.10
                contributions["month_end_shortage_delay"] = me_penalty
                neg_factors.append("Month-end liquidity shortage; recovery timing sensitive")

        # 5. Multiple Attempts Friction Penalty
        if features.attempt_number > 1:
            att_penalty = -min(0.30, 0.12 * (features.attempt_number - 1))
            contributions["prior_attempts_exhaustion"] = round(att_penalty, 3)
            neg_factors.append(f"Payment already attempted {features.attempt_number} times")

        # 6. High Risk / Block Penalty
        if cat == NormalizedFailureCategory.HARD_FAILURE:
            contributions["terminal_failure_block"] = -0.50
            neg_factors.append("Instrument or account is permanently blocked/cancelled")
        elif cat == NormalizedFailureCategory.HIGH_RISK:
            contributions["risk_velocity_block"] = -0.35
            neg_factors.append("Gateway risk or anomaly velocity flag triggered")

        # 7. Category Specific Positive Drivers
        if cat == NormalizedFailureCategory.TRANSIENT:
            pos_factors.append("Transient infrastructure timeout represents highly recoverable event")
        elif cat == NormalizedFailureCategory.AUTHENTICATION:
            pos_factors.append("Authentication drop-off recoverable via low-friction reminder")
        elif cat == NormalizedFailureCategory.ABANDONMENT and features.checkout_stage in ("OTP_STAGE", "PAYMENT_SUBMISSION"):
            pos_factors.append("Late-stage checkout abandonment indicates high purchase intent")

        # 8. Calculate Final Calibrated Score
        raw_score = base_prior + sum(v for k, v in contributions.items() if k != "base_category_prior")
        calibrated_score = round(min(0.99, max(0.01, raw_score)), 4)

        # 9. Assign Tier
        if calibrated_score >= 0.70:
            tier = RecoverabilityTier.HIGH
        elif calibrated_score >= 0.40:
            tier = RecoverabilityTier.MEDIUM
        else:
            tier = RecoverabilityTier.LOW

        return calibrated_score, tier, contributions, pos_factors, neg_factors

    @classmethod
    def _get_category_base_prior(cls, f: ReviveFeatures) -> float:
        cat = f.failure_category
        if cat == NormalizedFailureCategory.TRANSIENT:
            return 0.85
        elif cat == NormalizedFailureCategory.AUTHENTICATION:
            return 0.76
        elif cat == NormalizedFailureCategory.PAYMENT_METHOD:
            return 0.80 if f.is_subscription else 0.58
        elif cat == NormalizedFailureCategory.BANK_DECLINE:
            return 0.74 if f.is_high_value else 0.62
        elif cat == NormalizedFailureCategory.INSUFFICIENT_FUNDS:
            return 0.60
        elif cat == NormalizedFailureCategory.ABANDONMENT:
            if f.checkout_stage in ("OTP_STAGE", "PAYMENT_SUBMISSION"):
                return 0.78
            elif f.checkout_stage == "AUTHENTICATION_STARTED":
                return 0.60
            else:
                return 0.25 # Early drop-off
        elif cat == NormalizedFailureCategory.HIGH_RISK:
            return 0.20
        elif cat == NormalizedFailureCategory.HARD_FAILURE:
            return 0.02
        else:
            return 0.40
