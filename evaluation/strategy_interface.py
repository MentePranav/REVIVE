"""
Standardized strategy interface for all REVIVE recovery agents and baselines.
Enforces a uniform protocol so any new strategy can be evaluated without modifying the benchmark engine.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Union

from evaluation.models import StrategyDecision
from simulator.public_schema import AbandonedCheckout, Customer, Transaction


class BaseStrategy(ABC):
    """Abstract base class for all revenue recovery strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique uppercase strategy identifier (e.g. 'NO_ACTION', 'NAIVE_RETRY', 'RULE_BASED', 'REVIVE')."""
        pass

    @abstractmethod
    def decide(
        self,
        event: Union[Transaction, AbandonedCheckout],
        customer: Optional[Customer],
        prior_actions_for_event: List[StrategyDecision]
    ) -> StrategyDecision:
        """
        Evaluates a single payment failure or abandoned checkout and selects a recovery action.

        CRITICAL CONSTRAINTS:
        - Strategy code must ONLY inspect public observable fields in `event` and `customer`.
        - Access to ground truth evaluation fields is strictly prohibited.
        - Strategy must not look ahead to future events.
        """
        pass
