"""
Ground-truth recoverability engine.
Generates evaluation-only causal recovery benchmarks and counterfactual outcomes.
"""

import random
from typing import Dict, List, Optional

from simulator.config import SimulatorConfig
from simulator.enums import (
    CustomerProfile,
    FailureCategory,
    PaymentStatus,
    RecoveryAction,
    RecoveryOutcome,
    CheckoutStage,
)
from simulator.ground_truth_schema import GroundTruthRecord
from simulator.public_schema import AbandonedCheckout, Customer, Transaction


class GroundTruthEngine:
    """Computes causal ground truth recoverability and counterfactual outcomes."""

    def __init__(self, config: SimulatorConfig, rng: random.Random):
        self.config = config
        self.rng = rng

    def generate_ground_truth_for_transactions(
        self,
        transactions: List[Transaction],
        customers_by_id: Dict[str, Customer]
    ) -> List[GroundTruthRecord]:
        records: List[GroundTruthRecord] = []

        for txn in transactions:
            if txn.status != PaymentStatus.FAILED:
                continue

            customer = customers_by_id.get(txn.customer_id)
            if not customer or not txn.failure_details:
                continue

            record = self._evaluate_transaction(txn, customer)
            records.append(record)

        return records

    def generate_ground_truth_for_checkouts(
        self,
        checkouts: List[AbandonedCheckout],
        customers_by_id: Dict[str, Customer]
    ) -> List[GroundTruthRecord]:
        records: List[GroundTruthRecord] = []

        for chk in checkouts:
            customer = customers_by_id.get(chk.customer_id)
            if not customer:
                continue

            record = self._evaluate_checkout(chk, customer)
            records.append(record)

        return records

    def _evaluate_transaction(self, txn: Transaction, customer: Customer) -> GroundTruthRecord:
        profile = customer.customer_profile
        cat = txn.failure_details.failure_category

        # Case 1: Organically Resolved / Late Success
        if txn.is_late_success:
            return GroundTruthRecord(
                event_id=txn.transaction_id,
                customer_id=customer.customer_id,
                ground_truth_recoverable=True,
                ground_truth_best_action=RecoveryAction.DO_NOTHING,
                ground_truth_recovery_probability=1.0,
                ground_truth_customer_friction=0.0,
                counterfactual_outcomes={
                    RecoveryAction.RETRY.value: RecoveryOutcome.ALREADY_RESOLVED.value,
                    RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.ALREADY_RESOLVED.value,
                    RecoveryAction.REMINDER.value: RecoveryOutcome.ALREADY_RESOLVED.value,
                    RecoveryAction.DO_NOTHING.value: RecoveryOutcome.ALREADY_RESOLVED.value,
                    RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.ALREADY_RESOLVED.value,
                },
                causal_explanation="Payment was captured organically shortly after transient delay. Interventions are redundant.",
                is_already_resolved=True
            )

        # Case 2: Transient Gateway Failure
        if cat == FailureCategory.TRANSIENT_GATEWAY_FAILURE:
            if profile in (CustomerProfile.RELIABLE, CustomerProfile.OCCASIONAL_FAILURE, CustomerProfile.SUBSCRIPTION):
                rec_prob = round(self.rng.uniform(0.85, 0.96), 4)
                recoverable = True
                best_action = RecoveryAction.RETRY
                friction = 0.05
                outcomes = {
                    RecoveryAction.RETRY.value: RecoveryOutcome.SUCCESS.value,
                    RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.SUCCESS.value,
                    RecoveryAction.REMINDER.value: RecoveryOutcome.NO_RESPONSE.value,
                    RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
                    RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.SUCCESS.value,
                }
                explanation = "Transient gateway timeout on reliable customer; immediate/short-delay automated retry succeeds."
            else:
                rec_prob = round(self.rng.uniform(0.55, 0.75), 4)
                recoverable = True
                best_action = RecoveryAction.RETRY
                friction = 0.15
                outcomes = {
                    RecoveryAction.RETRY.value: RecoveryOutcome.SUCCESS.value if self.rng.random() < 0.70 else RecoveryOutcome.FAILURE.value,
                    RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.SUCCESS.value if self.rng.random() < 0.60 else RecoveryOutcome.FAILURE.value,
                    RecoveryAction.REMINDER.value: RecoveryOutcome.NO_RESPONSE.value,
                    RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
                    RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.FAILURE.value,
                }
                explanation = "Transient gateway timeout on customer with mixed payment history; moderate retry success rate."

        # Case 3: Insufficient Funds
        elif cat == FailureCategory.INSUFFICIENT_FUNDS:
            if profile in (CustomerProfile.RELIABLE, CustomerProfile.SUBSCRIPTION):
                rec_prob = round(self.rng.uniform(0.65, 0.82), 4)
                recoverable = True
                best_action = RecoveryAction.PAYMENT_LINK
                friction = 0.20
                outcomes = {
                    RecoveryAction.RETRY.value: RecoveryOutcome.FAILURE.value,  # Immediate retry fails because funds haven't changed
                    RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.SUCCESS.value,  # Link allows alternate instrument or delayed payment
                    RecoveryAction.REMINDER.value: RecoveryOutcome.SUCCESS.value,
                    RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
                    RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.FAILURE.value,
                }
                explanation = "Temporary fund shortage on loyal customer; immediate retry fails, but payment link with alternate options succeeds."
            else:
                rec_prob = round(self.rng.uniform(0.20, 0.40), 4)
                recoverable = self.rng.random() < 0.35
                best_action = RecoveryAction.PAYMENT_LINK if recoverable else RecoveryAction.DO_NOTHING
                friction = 0.35
                outcomes = {
                    RecoveryAction.RETRY.value: RecoveryOutcome.FAILURE.value,
                    RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.SUCCESS.value if recoverable else RecoveryOutcome.NO_RESPONSE.value,
                    RecoveryAction.REMINDER.value: RecoveryOutcome.NO_RESPONSE.value,
                    RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
                    RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.FAILURE.value,
                }
                explanation = "Persistent balance deficiency; immediate retries fail repeatedly."

        # Case 4: Bank Decline
        elif cat == FailureCategory.BANK_DECLINE:
            if profile == CustomerProfile.HIGH_VALUE:
                rec_prob = round(self.rng.uniform(0.70, 0.88), 4)
                recoverable = True
                best_action = RecoveryAction.HUMAN_REVIEW if txn.amount > 50000.0 else RecoveryAction.PAYMENT_LINK
                friction = 0.15
                outcomes = {
                    RecoveryAction.RETRY.value: RecoveryOutcome.FAILURE.value,
                    RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.SUCCESS.value,
                    RecoveryAction.REMINDER.value: RecoveryOutcome.NO_RESPONSE.value,
                    RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
                    RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.SUCCESS.value,
                }
                explanation = "High-value bank authorization limit; human outreach or corporate netbanking link required."
            elif profile in (CustomerProfile.RELIABLE, CustomerProfile.OCCASIONAL_FAILURE):
                rec_prob = round(self.rng.uniform(0.60, 0.78), 4)
                recoverable = True
                best_action = RecoveryAction.PAYMENT_LINK
                friction = 0.20
                outcomes = {
                    RecoveryAction.RETRY.value: RecoveryOutcome.FAILURE.value,
                    RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.SUCCESS.value,
                    RecoveryAction.REMINDER.value: RecoveryOutcome.SUCCESS.value,
                    RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
                    RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.FAILURE.value,
                }
                explanation = "Bank declined transaction; customer needs to switch card or authorize with bank via link."
            else:
                rec_prob = round(self.rng.uniform(0.15, 0.35), 4)
                recoverable = False
                best_action = RecoveryAction.DO_NOTHING
                friction = 0.40
                outcomes = {
                    RecoveryAction.RETRY.value: RecoveryOutcome.FAILURE.value,
                    RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.NO_RESPONSE.value,
                    RecoveryAction.REMINDER.value: RecoveryOutcome.NO_RESPONSE.value,
                    RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
                    RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.FAILURE.value,
                }
                explanation = "Repeated bank rejection indicating restricted account or chronic delinquency."

        # Case 5: Authentication Failure
        elif cat == FailureCategory.AUTHENTICATION_FAILURE:
            rec_prob = round(self.rng.uniform(0.65, 0.85), 4)
            recoverable = True
            best_action = RecoveryAction.REMINDER
            friction = 0.10
            outcomes = {
                RecoveryAction.RETRY.value: RecoveryOutcome.FAILURE.value,
                RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.SUCCESS.value,
                RecoveryAction.REMINDER.value: RecoveryOutcome.SUCCESS.value,
                RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
                RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.FAILURE.value,
            }
            explanation = "Customer dropped during 3DS/OTP verification; lightweight friction-free reminder prompts re-entry."

        # Case 6: Payment Method Failure (Expired Card, Invalid VPA)
        elif cat == FailureCategory.PAYMENT_METHOD_FAILURE:
            if profile == CustomerProfile.SUBSCRIPTION:
                rec_prob = round(self.rng.uniform(0.75, 0.90), 4)
                recoverable = True
                best_action = RecoveryAction.PAYMENT_LINK
                friction = 0.15
                outcomes = {
                    RecoveryAction.RETRY.value: RecoveryOutcome.FAILURE.value,  # Retrying same expired card will never work
                    RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.SUCCESS.value,  # Link allows updating mandate/card
                    RecoveryAction.REMINDER.value: RecoveryOutcome.NO_RESPONSE.value,
                    RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
                    RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.SUCCESS.value,
                }
                explanation = "Mandate instrument expired on subscription; payment link allows customer to replace card instrument."
            else:
                rec_prob = round(self.rng.uniform(0.40, 0.60), 4)
                recoverable = self.rng.random() < 0.50
                best_action = RecoveryAction.PAYMENT_LINK if recoverable else RecoveryAction.DO_NOTHING
                friction = 0.30
                outcomes = {
                    RecoveryAction.RETRY.value: RecoveryOutcome.FAILURE.value,
                    RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.SUCCESS.value if recoverable else RecoveryOutcome.FAILURE.value,
                    RecoveryAction.REMINDER.value: RecoveryOutcome.NO_RESPONSE.value,
                    RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
                    RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.FAILURE.value,
                }
                explanation = "Instrument invalid; customer must provide alternate payment method."

        # Case 7: Hard Failure
        elif cat == FailureCategory.HARD_FAILURE:
            rec_prob = round(self.rng.uniform(0.00, 0.05), 4)
            recoverable = False
            best_action = RecoveryAction.DO_NOTHING
            friction = 0.80
            outcomes = {
                RecoveryAction.RETRY.value: RecoveryOutcome.FAILURE.value,
                RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.FAILURE.value,
                RecoveryAction.REMINDER.value: RecoveryOutcome.NO_RESPONSE.value,
                RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
                RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.FAILURE.value,
            }
            explanation = "Permanently blocked or cancelled account; automated recovery prohibited."

        # Case 8: High Risk
        elif cat == FailureCategory.HIGH_RISK:
            rec_prob = round(self.rng.uniform(0.10, 0.30), 4)
            recoverable = False
            best_action = RecoveryAction.HUMAN_REVIEW
            friction = 0.90
            outcomes = {
                RecoveryAction.RETRY.value: RecoveryOutcome.FAILURE.value,
                RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.FAILURE.value,
                RecoveryAction.REMINDER.value: RecoveryOutcome.NO_RESPONSE.value,
                RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
                RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.SUCCESS.value if self.rng.random() < 0.30 else RecoveryOutcome.FAILURE.value,
            }
            explanation = "High risk anomaly flagged by gateway; requires compliance/risk team review before action."

        else:
            rec_prob = 0.50
            recoverable = True
            best_action = RecoveryAction.PAYMENT_LINK
            friction = 0.25
            outcomes = {
                RecoveryAction.RETRY.value: RecoveryOutcome.FAILURE.value,
                RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.SUCCESS.value,
                RecoveryAction.REMINDER.value: RecoveryOutcome.NO_RESPONSE.value,
                RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
                RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.FAILURE.value,
            }
            explanation = "Standard recovery path."

        return GroundTruthRecord(
            event_id=txn.transaction_id,
            customer_id=customer.customer_id,
            ground_truth_recoverable=recoverable,
            ground_truth_best_action=best_action,
            ground_truth_recovery_probability=rec_prob,
            ground_truth_customer_friction=friction,
            counterfactual_outcomes=outcomes,
            causal_explanation=explanation,
            is_already_resolved=False
        )

    def _evaluate_checkout(self, chk: AbandonedCheckout, customer: Customer) -> GroundTruthRecord:
        profile = customer.customer_profile
        stage = chk.checkout_stage

        # OTP stage abandonment on reliable customer has high intent
        if stage in (CheckoutStage.OTP_STAGE, CheckoutStage.PAYMENT_SUBMISSION) and profile in (CustomerProfile.RELIABLE, CustomerProfile.SUBSCRIPTION, CustomerProfile.HIGH_VALUE):
            rec_prob = round(self.rng.uniform(0.70, 0.88), 4)
            recoverable = True
            best_action = RecoveryAction.REMINDER
            friction = 0.08
            outcomes = {
                RecoveryAction.RETRY.value: RecoveryOutcome.FAILURE.value,
                RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.SUCCESS.value,
                RecoveryAction.REMINDER.value: RecoveryOutcome.SUCCESS.value,
                RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
                RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.FAILURE.value,
            }
            explanation = "High purchase intent abandoned at OTP stage; gentle push or reminder link recaptures session."
        elif stage == CheckoutStage.CHECKOUT_STARTED or profile == CustomerProfile.NEW_CUSTOMER:
            rec_prob = round(self.rng.uniform(0.10, 0.30), 4)
            recoverable = False
            best_action = RecoveryAction.DO_NOTHING
            friction = 0.40
            outcomes = {
                RecoveryAction.RETRY.value: RecoveryOutcome.FAILURE.value,
                RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.NO_RESPONSE.value,
                RecoveryAction.REMINDER.value: RecoveryOutcome.NO_RESPONSE.value,
                RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
                RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.FAILURE.value,
            }
            explanation = "Early funnel browsing drop-off; low recovery probability, high friction if contacted."
        else:
            rec_prob = round(self.rng.uniform(0.40, 0.60), 4)
            recoverable = self.rng.random() < 0.50
            best_action = RecoveryAction.REMINDER if recoverable else RecoveryAction.DO_NOTHING
            friction = 0.20
            outcomes = {
                RecoveryAction.RETRY.value: RecoveryOutcome.FAILURE.value,
                RecoveryAction.PAYMENT_LINK.value: RecoveryOutcome.SUCCESS.value if recoverable else RecoveryOutcome.NO_RESPONSE.value,
                RecoveryAction.REMINDER.value: RecoveryOutcome.SUCCESS.value if recoverable else RecoveryOutcome.NO_RESPONSE.value,
                RecoveryAction.DO_NOTHING.value: RecoveryOutcome.FAILURE.value,
                RecoveryAction.HUMAN_REVIEW.value: RecoveryOutcome.FAILURE.value,
            }
            explanation = "Mid-funnel payment method selection drop-off."

        return GroundTruthRecord(
            event_id=chk.checkout_id,
            customer_id=customer.customer_id,
            ground_truth_recoverable=recoverable,
            ground_truth_best_action=best_action,
            ground_truth_recovery_probability=rec_prob,
            ground_truth_customer_friction=friction,
            counterfactual_outcomes=outcomes,
            causal_explanation=explanation,
            is_already_resolved=False
        )
