"""
Abandoned checkout event generator across multi-step checkout funnels.
"""

import random
from datetime import datetime, timedelta
from typing import List

from simulator.config import SimulatorConfig
from simulator.enums import CheckoutStage, CustomerProfile, PaymentMethod
from simulator.public_schema import AbandonedCheckout, Customer


class CheckoutGenerator:
    """Generates realistic abandoned checkout sessions across distinct funnel stages."""

    def __init__(self, config: SimulatorConfig, rng: random.Random):
        self.config = config
        self.rng = rng

    def generate_abandoned_checkouts(
        self,
        customers: List[Customer],
        count: int | None = None
    ) -> List[AbandonedCheckout]:
        # Default ~6-10% relative to transaction volume
        total_checkouts = count if count is not None else max(10, int(self.config.transaction_count * 0.08))
        checkouts: List[AbandonedCheckout] = []

        base_start = datetime.fromisoformat(self.config.start_date.replace("Z", "+00:00"))
        sim_duration = timedelta(days=self.config.simulation_days)

        for i in range(1, total_checkouts + 1):
            chk_id = f"chk_{i:08d}"
            customer = self.rng.choice(customers)

            # Sample funnel drop-off stage
            stage = self.rng.choices(
                [
                    CheckoutStage.CHECKOUT_STARTED,
                    CheckoutStage.PAYMENT_METHOD_SELECTED,
                    CheckoutStage.AUTHENTICATION_STARTED,
                    CheckoutStage.OTP_STAGE,
                    CheckoutStage.PAYMENT_SUBMISSION,
                ],
                weights=[0.30, 0.25, 0.15, 0.20, 0.10],
                k=1
            )[0]

            # Payment method is only known if user advanced past stage 1
            selected_method = None
            if stage != CheckoutStage.CHECKOUT_STARTED:
                selected_method = customer.preferred_payment_method

            # Time spent in seconds correlated with funnel depth
            if stage == CheckoutStage.CHECKOUT_STARTED:
                time_spent = self.rng.randint(5, 35)
            elif stage == CheckoutStage.PAYMENT_METHOD_SELECTED:
                time_spent = self.rng.randint(25, 75)
            elif stage == CheckoutStage.AUTHENTICATION_STARTED:
                time_spent = self.rng.randint(45, 120)
            elif stage == CheckoutStage.OTP_STAGE:
                time_spent = self.rng.randint(60, 240)
            else:  # PAYMENT_SUBMISSION
                time_spent = self.rng.randint(90, 360)

            # Amount
            if customer.customer_profile == CustomerProfile.HIGH_VALUE:
                amount = round(self.rng.uniform(10000.0, 85000.0), 2)
            else:
                amount = round(self.rng.uniform(199.0, 4999.0), 2)

            offset_seconds = self.rng.randint(0, int(sim_duration.total_seconds()))
            chk_time = base_start + timedelta(seconds=offset_seconds)

            checkouts.append(AbandonedCheckout(
                checkout_id=chk_id,
                customer_id=customer.customer_id,
                created_at=chk_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                amount=amount,
                currency="INR",
                payment_method_selected=selected_method,
                checkout_stage=stage,
                time_spent_seconds=time_spent,
                is_abandoned=True
            ))

        checkouts.sort(key=lambda c: c.created_at)
        return checkouts
