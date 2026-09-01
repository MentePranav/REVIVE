"""
REVIVE Strategy Adapter for the Benchmark Evaluation Pipeline.
Wraps the ReviveEngine intelligence layer to conform to the BaseStrategy protocol.
"""

from typing import List, Optional, Union

from agent.engine import ReviveEngine
from evaluation.models import StrategyDecision
from evaluation.strategy_interface import BaseStrategy
from simulator.enums import PaymentStatus, RecoveryAction
from simulator.public_schema import AbandonedCheckout, Customer, Transaction


class ReviveStrategy(BaseStrategy):
    """
    REVIVE Strategy Adapter.
    Uses the Phase 4 contextual diagnosis and expected value scoring engine to select optimal actions.
    """

    @property
    def name(self) -> str:
        return "REVIVE"

    def decide(
        self,
        event: Union[Transaction, AbandonedCheckout],
        customer: Optional[Customer],
        prior_actions_for_event: List[StrategyDecision]
    ) -> StrategyDecision:
        event_id = event.transaction_id if isinstance(event, Transaction) else event.checkout_id
        timestamp = event.created_at

        # 1. Check if transaction is already in SUCCESS state
        if isinstance(event, Transaction) and event.status == PaymentStatus.SUCCESS:
            return StrategyDecision(
                strategy_name=self.name,
                event_id=event_id,
                customer_id=event.customer_id,
                action=RecoveryAction.DO_NOTHING,
                rule_id="REVIVE_SUCCESS_SKIP",
                reason="Transaction is already in SUCCESS state.",
                timestamp=timestamp,
                eligible=False,
                attempt_number=1
            )

        # 2. Check if intervention budget already exhausted
        active_prior = [a for a in prior_actions_for_event if a.action != RecoveryAction.DO_NOTHING]
        if len(active_prior) >= 2:
            return StrategyDecision(
                strategy_name=self.name,
                event_id=event_id,
                customer_id=event.customer_id,
                action=RecoveryAction.DO_NOTHING,
                rule_id="REVIVE_MAX_ATTEMPTS_EXHAUSTED",
                reason="Maximum recovery intervention attempts already exhausted for this opportunity.",
                timestamp=timestamp,
                eligible=False,
                attempt_number=len(prior_actions_for_event) + 1
            )

        # 3. Execute REVIVE Contextual Intelligence Engine
        rec = ReviveEngine.evaluate(event, customer)

        reason_str = (
            f"Diagnosis: {rec.diagnosis.category.value} (conf={rec.diagnosis.confidence:.2f}, "
            f"rec_score={rec.recoverability_score:.2f}, risk={rec.diagnosis.risk_signal.value}). "
            f"Top driver: {rec.top_positive_factors[0] if rec.top_positive_factors else rec.diagnosis.explanation}"
        )

        return StrategyDecision(
            strategy_name=self.name,
            event_id=event_id,
            customer_id=event.customer_id,
            action=rec.recommended_action,
            rule_id=f"REVIVE_DIAG_{rec.diagnosis.category.value}",
            reason=reason_str,
            timestamp=timestamp,
            eligible=True,
            attempt_number=len(prior_actions_for_event) + 1
        )
