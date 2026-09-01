"""
Baseline A: No-Action Strategy.
Never performs active recovery interventions. Establishes organic/natural recovery baseline.
"""

from typing import List, Optional, Union

from evaluation.models import StrategyDecision
from evaluation.strategy_interface import BaseStrategy
from simulator.enums import RecoveryAction
from simulator.public_schema import AbandonedCheckout, Customer, Transaction


class NoActionStrategy(BaseStrategy):
    """Establishes the natural baseline where zero automated interventions are executed."""

    @property
    def name(self) -> str:
        return "NO_ACTION"

    def decide(
        self,
        event: Union[Transaction, AbandonedCheckout],
        customer: Optional[Customer],
        prior_actions_for_event: List[StrategyDecision]
    ) -> StrategyDecision:
        event_id = event.transaction_id if isinstance(event, Transaction) else event.checkout_id
        timestamp = event.created_at

        return StrategyDecision(
            strategy_name=self.name,
            event_id=event_id,
            customer_id=event.customer_id,
            action=RecoveryAction.DO_NOTHING,
            rule_id="R000_NO_ACTION",
            reason="Passive observation; no active recovery intervention executed.",
            timestamp=timestamp,
            eligible=True,
            attempt_number=len(prior_actions_for_event) + 1
        )
