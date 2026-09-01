"""
Outcome simulation evaluator.
Determines resolution outcome, financial recovery, and costs for a given strategy decision against hidden ground truth.
"""

from typing import Optional, Union

from evaluation.models import ActionCostConfig, EvaluationOutcomeRecord, StrategyDecision
from simulator.enums import RecoveryAction, RecoveryOutcome
from simulator.ground_truth_schema import GroundTruthRecord
from simulator.public_schema import AbandonedCheckout, Transaction


class OutcomeEvaluator:
    """Evaluates strategy decisions against hidden ground truth records without data leakage."""

    def __init__(self, cost_config: Optional[ActionCostConfig] = None):
        self.cost_config = cost_config or ActionCostConfig()

    def evaluate_decision(
        self,
        decision: StrategyDecision,
        event: Union[Transaction, AbandonedCheckout],
        ground_truth: Optional[GroundTruthRecord]
    ) -> EvaluationOutcomeRecord:
        amount = event.amount
        action = decision.action
        cost = self.cost_config.get_cost(action)

        # If no ground truth exists (e.g. transaction was already SUCCESS)
        if ground_truth is None:
            return EvaluationOutcomeRecord(
                decision=decision,
                amount=amount,
                simulated_outcome=RecoveryOutcome.SUCCESS if (isinstance(event, Transaction) and event.status.value == "SUCCESS") else RecoveryOutcome.NO_RESPONSE,
                recovered_amount=0.0,
                action_cost=cost,
                is_recovered=False,
                is_incremental=False,
                is_false_positive=False
            )

        # 1. Handle Organically Resolved / Late Success
        if ground_truth.is_already_resolved:
            # Revenue recovered naturally regardless of action
            return EvaluationOutcomeRecord(
                decision=decision,
                amount=amount,
                simulated_outcome=RecoveryOutcome.ALREADY_RESOLVED,
                recovered_amount=amount,
                action_cost=cost,
                is_recovered=True,
                is_incremental=False, # Not incremental because it recovered organically
                is_false_positive=(action != RecoveryAction.DO_NOTHING) # Active intervention was redundant
            )

        # 2. Check Counterfactual Outcome Matrix for the chosen action
        action_key = action.value
        outcome_str = ground_truth.counterfactual_outcomes.get(action_key, RecoveryOutcome.FAILURE.value)
        outcome = RecoveryOutcome(outcome_str)

        # 3. Calculate Financial Yield
        if outcome == RecoveryOutcome.SUCCESS:
            recovered_amount = amount
            is_recovered = True
            is_incremental = (action != RecoveryAction.DO_NOTHING)
            is_false_positive = False
        else:
            recovered_amount = 0.0
            is_recovered = False
            is_incremental = False
            # If strategy performed an active intervention but failed to recover revenue
            is_false_positive = (action != RecoveryAction.DO_NOTHING)

        return EvaluationOutcomeRecord(
            decision=decision,
            amount=amount,
            simulated_outcome=outcome,
            recovered_amount=recovered_amount,
            action_cost=cost,
            is_recovered=is_recovered,
            is_incremental=is_incremental,
            is_false_positive=is_false_positive
        )
