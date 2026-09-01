"""
Action Value & Expected Revenue Scorer for REVIVE.
Computes context-conditional success probabilities and mathematical Expected Value (EV) per candidate action.
"""

from typing import Dict
from agent.models import (
    ActionScore,
    DiagnosisResult,
    NormalizedFailureCategory,
    ReviveFeatures,
)
from simulator.enums import RecoveryAction


class ActionScorer:
    """Evaluates expected financial yield and execution costs across the candidate action space."""

    # Synthetic unit execution costs (in INR)
    ACTION_COSTS = {
        RecoveryAction.DO_NOTHING: 0.0,
        RecoveryAction.RETRY: 2.0,
        RecoveryAction.REMINDER: 1.5,
        RecoveryAction.PAYMENT_LINK: 3.0,
        RecoveryAction.HUMAN_REVIEW: 50.0,
    }

    @classmethod
    def score_all_actions(
        cls,
        features: ReviveFeatures,
        diagnosis: DiagnosisResult,
        recoverability_score: float
    ) -> Dict[str, ActionScore]:
        scores: Dict[str, ActionScore] = {}
        all_actions = [
            RecoveryAction.DO_NOTHING,
            RecoveryAction.RETRY,
            RecoveryAction.REMINDER,
            RecoveryAction.PAYMENT_LINK,
            RecoveryAction.HUMAN_REVIEW,
        ]

        for action in all_actions:
            score = cls._score_single_action(action, features, diagnosis, recoverability_score)
            scores[action.value] = score

        return scores

    @classmethod
    def _score_single_action(
        cls,
        action: RecoveryAction,
        features: ReviveFeatures,
        diagnosis: DiagnosisResult,
        rec_score: float
    ) -> ActionScore:
        amount = features.amount
        cat = features.failure_category
        cost = cls.ACTION_COSTS.get(action, 0.0)

        # 1. Determine Action Eligibility
        is_eligible = True
        if action == RecoveryAction.RETRY:
            # Cannot retry abandoned checkouts or hard terminal declines
            if features.is_abandoned or cat == NormalizedFailureCategory.HARD_FAILURE:
                is_eligible = False

        if action == RecoveryAction.HUMAN_REVIEW and amount < 5000.0 and cat != NormalizedFailureCategory.HIGH_RISK:
            # Human review economically ineligible for low-value non-risk transactions
            is_eligible = False

        # 2. Compute Contextual Success Probability P(success | action, context)
        if not is_eligible or action == RecoveryAction.DO_NOTHING:
            p_success = 0.0
            friction = 0.0
        elif cat == NormalizedFailureCategory.HARD_FAILURE:
            p_success = 0.0
            friction = 10.0
        elif cat == NormalizedFailureCategory.TRANSIENT:
            if action == RecoveryAction.RETRY:
                p_success = min(0.98, rec_score * 1.05)
                friction = 0.5
            elif action == RecoveryAction.PAYMENT_LINK:
                p_success = min(0.90, rec_score * 0.95)
                friction = 2.0
            elif action == RecoveryAction.REMINDER:
                p_success = min(0.40, rec_score * 0.45)
                friction = 1.0
            elif action == RecoveryAction.HUMAN_REVIEW:
                p_success = min(0.95, rec_score * 0.98)
                friction = 5.0
            else:
                p_success = 0.0
                friction = 0.0

        elif cat == NormalizedFailureCategory.INSUFFICIENT_FUNDS:
            if action == RecoveryAction.RETRY:
                # Immediate retry on insufficient funds has low success probability
                p_success = 0.08
                friction = 4.0
            elif action == RecoveryAction.PAYMENT_LINK:
                # Payment link allows customer to use alternate card/account
                p_success = min(0.92, rec_score * 1.10)
                friction = 1.5
            elif action == RecoveryAction.REMINDER:
                p_success = min(0.75, rec_score * 0.90)
                friction = 1.0
            elif action == RecoveryAction.HUMAN_REVIEW:
                p_success = min(0.70, rec_score * 0.85)
                friction = 5.0
            else:
                p_success = 0.0
                friction = 0.0

        elif cat == NormalizedFailureCategory.AUTHENTICATION:
            if action == RecoveryAction.RETRY:
                p_success = 0.05 # Retrying dropped 3DS without user input fails
                friction = 3.0
            elif action == RecoveryAction.REMINDER:
                p_success = min(0.95, rec_score * 1.15)
                friction = 0.5
            elif action == RecoveryAction.PAYMENT_LINK:
                p_success = min(0.90, rec_score * 1.05)
                friction = 1.5
            elif action == RecoveryAction.HUMAN_REVIEW:
                p_success = min(0.80, rec_score * 0.90)
                friction = 5.0
            else:
                p_success = 0.0
                friction = 0.0

        elif cat == NormalizedFailureCategory.PAYMENT_METHOD:
            if action == RecoveryAction.RETRY:
                p_success = 0.02 # Retrying expired instrument fails
                friction = 5.0
            elif action == RecoveryAction.PAYMENT_LINK:
                p_success = min(0.94, rec_score * 1.15)
                friction = 1.0
            elif action == RecoveryAction.REMINDER:
                p_success = min(0.35, rec_score * 0.40)
                friction = 1.0
            elif action == RecoveryAction.HUMAN_REVIEW:
                p_success = min(0.85, rec_score * 0.95)
                friction = 5.0
            else:
                p_success = 0.0
                friction = 0.0

        elif cat == NormalizedFailureCategory.BANK_DECLINE:
            if action == RecoveryAction.HUMAN_REVIEW and (features.is_high_value or amount >= 50000.0):
                p_success = min(0.92, rec_score * 1.10)
                friction = 2.0
            elif action == RecoveryAction.PAYMENT_LINK:
                p_success = min(0.88, rec_score * 1.05)
                friction = 1.5
            elif action == RecoveryAction.RETRY:
                p_success = 0.15
                friction = 3.0
            elif action == RecoveryAction.REMINDER:
                p_success = min(0.40, rec_score * 0.45)
                friction = 1.0
            else:
                p_success = 0.0
                friction = 0.0

        elif cat == NormalizedFailureCategory.ABANDONMENT:
            if features.checkout_stage in ("OTP_STAGE", "PAYMENT_SUBMISSION"):
                if action == RecoveryAction.REMINDER:
                    p_success = min(0.92, rec_score * 1.15)
                    friction = 0.5
                elif action == RecoveryAction.PAYMENT_LINK:
                    p_success = min(0.88, rec_score * 1.05)
                    friction = 1.5
                else:
                    p_success = 0.0
                    friction = 2.0
            else:
                if action == RecoveryAction.REMINDER:
                    p_success = min(0.30, rec_score * 0.80)
                    friction = 2.0
                elif action == RecoveryAction.PAYMENT_LINK:
                    p_success = min(0.25, rec_score * 0.70)
                    friction = 2.5
                else:
                    p_success = 0.0
                    friction = 0.0

        elif cat == NormalizedFailureCategory.HIGH_RISK:
            if action == RecoveryAction.HUMAN_REVIEW:
                p_success = min(0.60, rec_score * 1.20)
                friction = 2.0
            else:
                p_success = 0.0
                friction = 10.0
        else:
            p_success = min(0.50, rec_score * 0.80)
            friction = 2.0

        # 3. Calculate Expected Financial Yield
        expected_revenue = round(p_success * amount, 2)
        expected_value = round(expected_revenue - cost - friction, 2) if is_eligible else -999.0

        return ActionScore(
            action=action,
            success_probability=round(p_success, 4),
            expected_revenue=expected_revenue,
            action_cost=cost,
            friction_penalty=friction,
            expected_value=expected_value,
            is_eligible=is_eligible
        )
