"""
Lifecycle and policy safety guards for strategy execution.
Enforces realistic intervention bounds across all strategies.
"""

from typing import List, Union
from evaluation.models import StrategyDecision
from simulator.enums import PaymentStatus, RecoveryAction
from simulator.public_schema import AbandonedCheckout, Transaction


class LifecycleGuard:
    """Validates whether a proposed strategy decision is permissible under basic lifecycle invariants."""

    @classmethod
    def is_eligible_for_intervention(
        cls,
        event: Union[Transaction, AbandonedCheckout],
        prior_actions: List[StrategyDecision]
    ) -> tuple[bool, str]:
        """
        Determines whether the given event can receive a recovery intervention.
        Returns (is_eligible, reason_if_ineligible).
        """
        # 1. Successful transactions are strictly ineligible
        if isinstance(event, Transaction) and event.status == PaymentStatus.SUCCESS:
            return False, "Transaction is already marked SUCCESS; intervention prohibited."

        # 2. Prevent infinite interventions per event (hard cap: max 3 attempts total)
        active_interventions = [
            a for a in prior_actions if a.action != RecoveryAction.DO_NOTHING
        ]
        if len(active_interventions) >= 3:
            return False, "Maximum allowable recovery intervention attempts (3) reached for this event."

        # 3. Check for terminal failure states
        if isinstance(event, Transaction) and event.failure_details:
            cat = event.failure_details.failure_category.value
            if cat == "HARD_FAILURE" and any(a.action != RecoveryAction.DO_NOTHING for a in prior_actions):
                return False, "Hard terminal failure has already been processed."

        return True, "Eligible"
