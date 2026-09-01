"""
Recommendation Engine for REVIVE.
Selects the economically optimal recovery intervention by maximizing Expected Value (EV).
"""

from typing import Dict, List, Optional
from agent.models import (
    ActionScore,
    DiagnosisResult,
    RecoverabilityTier,
    ReviveFeatures,
    ReviveRecommendation,
)
from simulator.enums import RecoveryAction


class RecommendationEngine:
    """Selects the highest expected-value recovery recommendation among eligible actions."""

    @classmethod
    def recommend(
        cls,
        features: ReviveFeatures,
        diagnosis: DiagnosisResult,
        recoverability_score: float,
        recoverability_tier: RecoverabilityTier,
        action_scores: Dict[str, ActionScore],
        feature_contributions: Dict[str, float],
        top_positive_factors: List[str],
        top_negative_factors: List[str],
        timestamp: str
    ) -> ReviveRecommendation:
        # 1. Filter eligible candidate actions
        eligible_scores = [
            score for score in action_scores.values()
            if score.is_eligible and score.expected_value > 0.0
        ]

        # 2. Select optimal action by maximizing Expected Value
        if eligible_scores:
            best_action_score = max(eligible_scores, key=lambda s: s.expected_value)
            chosen_action = best_action_score.action
        else:
            # If no eligible action yields positive expected value -> DO_NOTHING
            chosen_action = RecoveryAction.DO_NOTHING

        return ReviveRecommendation(
            event_id=features.event_id,
            payment_id=f"pay_{features.event_id.replace('txn_', '').replace('chk_', '')}",
            customer_id=features.customer_id,
            timestamp=timestamp,
            amount=features.amount,
            diagnosis=diagnosis,
            recoverability_score=recoverability_score,
            recoverability_tier=recoverability_tier,
            recommended_action=chosen_action,
            action_scores=action_scores,
            feature_contributions=feature_contributions,
            top_positive_factors=top_positive_factors,
            top_negative_factors=top_negative_factors
        )
