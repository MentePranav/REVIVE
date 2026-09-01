"""
Baseline B: Naive Retry Strategy.
Attempts a single indiscriminate payment retry for every failed transaction.
"""

from typing import List, Optional, Union

from evaluation.models import StrategyDecision
from evaluation.strategy_interface import BaseStrategy
from simulator.enums import FailureCategory, PaymentStatus, RecoveryAction
from simulator.public_schema import AbandonedCheckout, Customer, Transaction


class NaiveRetryStrategy(BaseStrategy):
    """
    Standard naive industry retry baseline.
    Attempts exactly ONE automated retry for any eligible failed transaction.
    """

    @property
    def name(self) -> str:
        return "NAIVE_RETRY"

    def decide(
        self,
        event: Union[Transaction, AbandonedCheckout],
        customer: Optional[Customer],
        prior_actions_for_event: List[StrategyDecision]
    ) -> StrategyDecision:
        event_id = event.transaction_id if isinstance(event, Transaction) else event.checkout_id
        timestamp = event.created_at

        # 1. Abandoned Checkouts cannot be retried via gateway retry
        if isinstance(event, AbandonedCheckout):
            return StrategyDecision(
                strategy_name=self.name,
                event_id=event_id,
                customer_id=event.customer_id,
                action=RecoveryAction.DO_NOTHING,
                rule_id="R_NAIVE_ABANDONED_SKIP",
                reason="Abandoned checkout has no authorized payment intent to retry.",
                timestamp=timestamp,
                eligible=False,
                attempt_number=1
            )

        # 2. Check if transaction is successful
        if event.status == PaymentStatus.SUCCESS:
            return StrategyDecision(
                strategy_name=self.name,
                event_id=event_id,
                customer_id=event.customer_id,
                action=RecoveryAction.DO_NOTHING,
                rule_id="R_NAIVE_SUCCESS_SKIP",
                reason="Payment already successful; no retry needed.",
                timestamp=timestamp,
                eligible=False,
                attempt_number=1
            )

        # 3. Check if retry already attempted (Single retry limit)
        prior_retries = [a for a in prior_actions_for_event if a.action == RecoveryAction.RETRY]
        if len(prior_retries) >= 1:
            return StrategyDecision(
                strategy_name=self.name,
                event_id=event_id,
                customer_id=event.customer_id,
                action=RecoveryAction.DO_NOTHING,
                rule_id="R_NAIVE_MAX_RETRY_REACHED",
                reason="Single retry attempt budget already exhausted for this payment.",
                timestamp=timestamp,
                eligible=False,
                attempt_number=len(prior_actions_for_event) + 1
            )

        # 4. Skip hard terminal failures where retry is impossible
        if event.failure_details and event.failure_details.failure_category == FailureCategory.HARD_FAILURE:
            return StrategyDecision(
                strategy_name=self.name,
                event_id=event_id,
                customer_id=event.customer_id,
                action=RecoveryAction.DO_NOTHING,
                rule_id="R_NAIVE_HARD_FAILURE_SKIP",
                reason="Hard terminal decline detected; retry disallowed.",
                timestamp=timestamp,
                eligible=False,
                attempt_number=1
            )

        # 5. Execute naive automated retry
        return StrategyDecision(
            strategy_name=self.name,
            event_id=event_id,
            customer_id=event.customer_id,
            action=RecoveryAction.RETRY,
            rule_id="R_NAIVE_GLOBAL_RETRY",
            reason="Standard naive single payment retry on failed transaction.",
            timestamp=timestamp,
            eligible=True,
            attempt_number=len(prior_actions_for_event) + 1
        )
