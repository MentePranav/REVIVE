"""
ReviveEngine: Primary entry point for the REVIVE contextual intelligence pipeline.
Coordinates Feature Extraction -> Diagnosis -> Recoverability Scoring -> Action EV Scoring -> Recommendation.
"""

from typing import Dict, List, Optional, Tuple, Union

from agent.action_scorer import ActionScorer
from agent.diagnostician import DiagnosticsEngine
from agent.features import FeatureExtractor
from agent.models import (
    BatchDiagnosisSummary,
    ReviveRecommendation,
)
from agent.recommender import RecommendationEngine
from agent.recoverability import RecoverabilityScorer
from simulator.enums import PaymentStatus
from simulator.public_schema import AbandonedCheckout, Customer, Transaction


class ReviveEngine:
    """Core REVIVE intelligence and recommendation engine."""

    @classmethod
    def evaluate(
        cls,
        event: Union[Transaction, AbandonedCheckout],
        customer: Optional[Customer]
    ) -> ReviveRecommendation:
        """Evaluates a single public payment failure or abandoned checkout."""
        # 1. Feature Extraction
        features = FeatureExtractor.extract_features(event, customer)

        # 2. Root-Cause Diagnosis
        diagnosis = DiagnosticsEngine.diagnose(features)

        # 3. Calibrated Recoverability Assessment
        rec_score, tier, contributions, pos_factors, neg_factors = (
            RecoverabilityScorer.score_recoverability(features, diagnosis)
        )

        # 4. Action Value & Expected Revenue Scoring
        action_scores = ActionScorer.score_all_actions(features, diagnosis, rec_score)

        # 5. Recommendation Selection
        timestamp = event.created_at
        return RecommendationEngine.recommend(
            features=features,
            diagnosis=diagnosis,
            recoverability_score=rec_score,
            recoverability_tier=tier,
            action_scores=action_scores,
            feature_contributions=contributions,
            top_positive_factors=pos_factors,
            top_negative_factors=neg_factors,
            timestamp=timestamp
        )

    @classmethod
    def evaluate_batch(
        cls,
        events: List[Union[Transaction, AbandonedCheckout]],
        customers_by_id: Dict[str, Customer]
    ) -> Tuple[List[ReviveRecommendation], BatchDiagnosisSummary]:
        """Processes a batch of payment failure and checkout opportunities."""
        recommendations: List[ReviveRecommendation] = []
        diag_counts: Dict[str, int] = {}
        action_counts: Dict[str, int] = {}
        tier_counts: Dict[str, int] = {}
        risk_counts: Dict[str, int] = {}

        total_rec_score = 0.0
        total_confidence = 0.0

        for event in events:
            # Skip non-failed transactions
            if isinstance(event, Transaction) and event.status == PaymentStatus.SUCCESS:
                continue

            customer = customers_by_id.get(event.customer_id)
            rec = cls.evaluate(event, customer)
            recommendations.append(rec)

            # Accumulate distributions
            cat_name = rec.diagnosis.category.value
            diag_counts[cat_name] = diag_counts.get(cat_name, 0) + 1

            act_name = rec.recommended_action.value
            action_counts[act_name] = action_counts.get(act_name, 0) + 1

            tier_name = rec.recoverability_tier.value
            tier_counts[tier_name] = tier_counts.get(tier_name, 0) + 1

            risk_name = rec.diagnosis.risk_signal.value
            risk_counts[risk_name] = risk_counts.get(risk_name, 0) + 1

            total_rec_score += rec.recoverability_score
            total_confidence += rec.diagnosis.confidence

        n = len(recommendations)
        summary = BatchDiagnosisSummary(
            total_opportunities=n,
            diagnosis_distribution=diag_counts,
            recommended_action_distribution=action_counts,
            recoverability_tier_distribution=tier_counts,
            risk_signal_distribution=risk_counts,
            average_recoverability_score=round((total_rec_score / n) if n > 0 else 0.0, 4),
            average_diagnosis_confidence=round((total_confidence / n) if n > 0 else 0.0, 4)
        )

        return recommendations, summary
