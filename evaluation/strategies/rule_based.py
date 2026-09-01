"""
Baseline C: Rule-Based Recovery Strategy.
Transparent heuristic decision engine mapping observable failure contexts to specialized recovery interventions.
"""

from typing import List, Optional, Union

from evaluation.models import StrategyDecision
from evaluation.strategy_interface import BaseStrategy
from simulator.enums import (
    CheckoutStage,
    CustomerProfile,
    FailureCategory,
    PaymentStatus,
    RecoveryAction,
)
from simulator.public_schema import AbandonedCheckout, Customer, Transaction


class RuleBasedStrategy(BaseStrategy):
    """
    Industry best-practice rule-based heuristic recovery strategy.
    Uses observable gateway error semantics, customer profiles, and amounts to assign bounded actions.
    """

    @property
    def name(self) -> str:
        return "RULE_BASED"

    def decide(
        self,
        event: Union[Transaction, AbandonedCheckout],
        customer: Optional[Customer],
        prior_actions_for_event: List[StrategyDecision]
    ) -> StrategyDecision:
        event_id = event.transaction_id if isinstance(event, Transaction) else event.checkout_id
        timestamp = event.created_at

        # Check if intervention budget already used
        active_prior = [a for a in prior_actions_for_event if a.action != RecoveryAction.DO_NOTHING]
        if len(active_prior) >= 2:
            return StrategyDecision(
                strategy_name=self.name,
                event_id=event_id,
                customer_id=event.customer_id,
                action=RecoveryAction.DO_NOTHING,
                rule_id="R_RULE_MAX_ATTEMPTS_EXHAUSTED",
                reason="Maximum rule-based intervention attempts (2) already exhausted.",
                timestamp=timestamp,
                eligible=False,
                attempt_number=len(prior_actions_for_event) + 1
            )

        # ----------------------------------------------------------------------
        # Handling Abandoned Checkouts
        # ----------------------------------------------------------------------
        if isinstance(event, AbandonedCheckout):
            stage = event.checkout_stage
            # If abandoned deep in the funnel (OTP or Payment Submission) -> send gentle Reminder
            if stage in (CheckoutStage.OTP_STAGE, CheckoutStage.PAYMENT_SUBMISSION, CheckoutStage.AUTHENTICATION_STARTED):
                return StrategyDecision(
                    strategy_name=self.name,
                    event_id=event_id,
                    customer_id=event.customer_id,
                    action=RecoveryAction.REMINDER,
                    rule_id="R006_ABANDONED_CHECKOUT_REMINDER",
                    reason="High purchase intent abandoned late in checkout funnel; dispatching reminder notification.",
                    timestamp=timestamp,
                    eligible=True,
                    attempt_number=len(prior_actions_for_event) + 1
                )
            else:
                # Early funnel browsing drop-off -> Avoid friction, do not intervene
                return StrategyDecision(
                    strategy_name=self.name,
                    event_id=event_id,
                    customer_id=event.customer_id,
                    action=RecoveryAction.DO_NOTHING,
                    rule_id="R006B_EARLY_ABANDONMENT_SKIP",
                    reason="Early funnel abandonment; skipping active intervention to avoid customer spam.",
                    timestamp=timestamp,
                    eligible=False,
                    attempt_number=1
                )

        # ----------------------------------------------------------------------
        # Handling Transactions
        # ----------------------------------------------------------------------
        if event.status == PaymentStatus.SUCCESS:
            return StrategyDecision(
                strategy_name=self.name,
                event_id=event_id,
                customer_id=event.customer_id,
                action=RecoveryAction.DO_NOTHING,
                rule_id="R000_SUCCESS_SKIP",
                reason="Transaction is already in SUCCESS state.",
                timestamp=timestamp,
                eligible=False,
                attempt_number=1
            )

        if not event.failure_details:
            return StrategyDecision(
                strategy_name=self.name,
                event_id=event_id,
                customer_id=event.customer_id,
                action=RecoveryAction.DO_NOTHING,
                rule_id="R_UNKNOWN_FAILURE_SKIP",
                reason="No failure details available to evaluate rules.",
                timestamp=timestamp,
                eligible=False,
                attempt_number=1
            )

        cat = event.failure_details.failure_category

        # Rule 1: Transient Gateway / Network Failures
        if cat == FailureCategory.TRANSIENT_GATEWAY_FAILURE:
            return StrategyDecision(
                strategy_name=self.name,
                event_id=event_id,
                customer_id=event.customer_id,
                action=RecoveryAction.RETRY,
                rule_id="R001_TRANSIENT_RETRY",
                reason="Transient gateway/network timeout detected; scheduling automated payment retry.",
                timestamp=timestamp,
                eligible=True,
                attempt_number=len(prior_actions_for_event) + 1
            )

        # Rule 2: Insufficient Funds
        if cat == FailureCategory.INSUFFICIENT_FUNDS:
            # Immediate retry will fail; send payment link allowing customer to use alternate card/account
            return StrategyDecision(
                strategy_name=self.name,
                event_id=event_id,
                customer_id=event.customer_id,
                action=RecoveryAction.PAYMENT_LINK,
                rule_id="R002_INSUFFICIENT_FUNDS_PAYMENT_LINK",
                reason="Insufficient balance decline; generating alternate payment link with multiple payment rails.",
                timestamp=timestamp,
                eligible=True,
                attempt_number=len(prior_actions_for_event) + 1
            )

        # Rule 3: Authentication Failures (3DS / OTP issues)
        if cat == FailureCategory.AUTHENTICATION_FAILURE:
            return StrategyDecision(
                strategy_name=self.name,
                event_id=event_id,
                customer_id=event.customer_id,
                action=RecoveryAction.REMINDER,
                rule_id="R003_AUTH_FAILURE_REMINDER",
                reason="Customer dropped during authentication/OTP; sending frictionless re-authorization reminder.",
                timestamp=timestamp,
                eligible=True,
                attempt_number=len(prior_actions_for_event) + 1
            )

        # Rule 4: Payment Method / Instrument Expiry or Inactivity
        if cat == FailureCategory.PAYMENT_METHOD_FAILURE:
            return StrategyDecision(
                strategy_name=self.name,
                event_id=event_id,
                customer_id=event.customer_id,
                action=RecoveryAction.PAYMENT_LINK,
                rule_id="R004_METHOD_FAILURE_PAYMENT_LINK",
                reason="Payment instrument expired or inactive; sending link to update/replace payment method.",
                timestamp=timestamp,
                eligible=True,
                attempt_number=len(prior_actions_for_event) + 1
            )

        # Rule 5: Bank Decline (Check for high-value threshold)
        if cat == FailureCategory.BANK_DECLINE:
            if event.amount >= 50000.0 or (customer and customer.customer_profile == CustomerProfile.HIGH_VALUE):
                return StrategyDecision(
                    strategy_name=self.name,
                    event_id=event_id,
                    customer_id=event.customer_id,
                    action=RecoveryAction.HUMAN_REVIEW,
                    rule_id="R005A_HIGH_VALUE_BANK_DECLINE_ESCALATE",
                    reason="High-value bank decline (>= INR 50k); routing to high-touch support queue.",
                    timestamp=timestamp,
                    eligible=True,
                    attempt_number=len(prior_actions_for_event) + 1
                )
            else:
                return StrategyDecision(
                    strategy_name=self.name,
                    event_id=event_id,
                    customer_id=event.customer_id,
                    action=RecoveryAction.PAYMENT_LINK,
                    rule_id="R005B_BANK_DECLINE_PAYMENT_LINK",
                    reason="Standard bank authorization decline; providing alternate payment link.",
                    timestamp=timestamp,
                    eligible=True,
                    attempt_number=len(prior_actions_for_event) + 1
                )

        # Rule 7: Hard Failure (Stolen card, closed account)
        if cat == FailureCategory.HARD_FAILURE:
            return StrategyDecision(
                strategy_name=self.name,
                event_id=event_id,
                customer_id=event.customer_id,
                action=RecoveryAction.DO_NOTHING,
                rule_id="R007_HARD_FAILURE_STOP",
                reason="Permanent instrument cancellation/block; automated recovery prohibited.",
                timestamp=timestamp,
                eligible=False,
                attempt_number=1
            )

        # Rule 8: High Risk Anomaly
        if cat == FailureCategory.HIGH_RISK:
            if event.amount >= 20000.0:
                return StrategyDecision(
                    strategy_name=self.name,
                    event_id=event_id,
                    customer_id=event.customer_id,
                    action=RecoveryAction.HUMAN_REVIEW,
                    rule_id="R008A_HIGH_RISK_MANUAL_REVIEW",
                    reason="High-risk velocity flag on significant amount; escalating to fraud/compliance review.",
                    timestamp=timestamp,
                    eligible=True,
                    attempt_number=len(prior_actions_for_event) + 1
                )
            else:
                return StrategyDecision(
                    strategy_name=self.name,
                    event_id=event_id,
                    customer_id=event.customer_id,
                    action=RecoveryAction.DO_NOTHING,
                    rule_id="R008B_HIGH_RISK_BLOCK",
                    reason="Risk anomaly flagged; skipping active intervention.",
                    timestamp=timestamp,
                    eligible=False,
                    attempt_number=1
                )

        # Fallback default
        return StrategyDecision(
            strategy_name=self.name,
            event_id=event_id,
            customer_id=event.customer_id,
            action=RecoveryAction.DO_NOTHING,
            rule_id="R_DEFAULT_FALLBACK_SKIP",
            reason="Unclassified failure mode; taking no action.",
            timestamp=timestamp,
            eligible=False,
            attempt_number=1
        )
