"""
Customer population generator with correlated behavioral profiles.
"""

import random
from datetime import datetime, timedelta
from typing import List

from simulator.config import SimulatorConfig
from simulator.enums import CustomerProfile, CustomerSegment, PaymentMethod
from simulator.public_schema import Customer


class CustomerGenerator:
    """Generates a heterogeneous customer population with correlated behavioral profiles."""

    def __init__(self, config: SimulatorConfig, rng: random.Random):
        self.config = config
        self.rng = rng

    def generate_population(self, count: int | None = None) -> List[Customer]:
        total_customers = count or self.config.customer_count
        customers: List[Customer] = []

        # Calculate counts per profile based on configured proportions
        profiles_list = list(self.config.profile_proportions.keys())
        proportions = [self.config.profile_proportions[p] for p in profiles_list]

        # Base simulation start date
        base_start = datetime.fromisoformat(self.config.start_date.replace("Z", "+00:00"))

        for i in range(1, total_customers + 1):
            cust_id = f"cust_{i:06d}"
            profile_str = self.rng.choices(profiles_list, weights=proportions, k=1)[0]
            profile = CustomerProfile(profile_str)

            customer = self._generate_single_customer(cust_id, profile, base_start)
            customers.append(customer)

        return customers

    def _generate_single_customer(
        self,
        cust_id: str,
        profile: CustomerProfile,
        base_start: datetime
    ) -> Customer:
        """Constructs an individual customer instance correlated with their profile."""
        
        if profile == CustomerProfile.RELIABLE:
            age_days = self.rng.randint(60, 730)
            segment = self.rng.choices(
                [CustomerSegment.CONSUMER_RETAIL, CustomerSegment.CONSUMER_PRO, CustomerSegment.SMB],
                weights=[0.50, 0.35, 0.15],
                k=1
            )[0]
            hist_txns = self.rng.randint(8, 50)
            sampled_rate = self.rng.uniform(0.90, 0.99)
            hist_success = int(round(hist_txns * sampled_rate))
            hist_failure = hist_txns - hist_success
            success_rate = round(hist_success / hist_txns, 4) if hist_txns > 0 else 1.0
            avg_amt = round(self.rng.uniform(399.0, 3500.0), 2)
            pref_method = self.rng.choices(
                [PaymentMethod.UPI, PaymentMethod.CARD, PaymentMethod.NETBANKING, PaymentMethod.WALLET],
                weights=[0.60, 0.25, 0.10, 0.05],
                k=1
            )[0]

        elif profile == CustomerProfile.OCCASIONAL_FAILURE:
            age_days = self.rng.randint(30, 365)
            segment = self.rng.choices(
                [CustomerSegment.CONSUMER_RETAIL, CustomerSegment.CONSUMER_PRO],
                weights=[0.70, 0.30],
                k=1
            )[0]
            hist_txns = self.rng.randint(5, 30)
            sampled_rate = self.rng.uniform(0.70, 0.85)
            hist_success = int(round(hist_txns * sampled_rate))
            hist_failure = hist_txns - hist_success
            success_rate = round(hist_success / hist_txns, 4) if hist_txns > 0 else 1.0
            avg_amt = round(self.rng.uniform(299.0, 2499.0), 2)
            pref_method = self.rng.choices(
                [PaymentMethod.UPI, PaymentMethod.CARD, PaymentMethod.WALLET],
                weights=[0.65, 0.20, 0.15],
                k=1
            )[0]

        elif profile == CustomerProfile.HIGH_FAILURE:
            age_days = self.rng.randint(15, 180)
            segment = CustomerSegment.CONSUMER_RETAIL
            hist_txns = self.rng.randint(3, 20)
            sampled_rate = self.rng.uniform(0.25, 0.50)
            hist_success = int(round(hist_txns * sampled_rate))
            hist_failure = hist_txns - hist_success
            success_rate = round(hist_success / hist_txns, 4) if hist_txns > 0 else 1.0
            avg_amt = round(self.rng.uniform(199.0, 1999.0), 2)
            pref_method = self.rng.choices(
                [PaymentMethod.UPI, PaymentMethod.CARD, PaymentMethod.WALLET],
                weights=[0.70, 0.15, 0.15],
                k=1
            )[0]

        elif profile == CustomerProfile.NEW_CUSTOMER:
            age_days = self.rng.randint(0, 14)
            segment = CustomerSegment.CONSUMER_RETAIL
            hist_txns = self.rng.choices([0, 1, 2], weights=[0.60, 0.30, 0.10], k=1)[0]
            if hist_txns == 0:
                hist_success = 0
                hist_failure = 0
                success_rate = 1.0
                avg_amt = round(self.rng.uniform(199.0, 1299.0), 2)
            else:
                hist_success = self.rng.randint(0, hist_txns)
                hist_failure = hist_txns - hist_success
                success_rate = round(hist_success / hist_txns, 4)
                avg_amt = round(self.rng.uniform(199.0, 1499.0), 2)
            pref_method = self.rng.choices(
                [PaymentMethod.UPI, PaymentMethod.CARD],
                weights=[0.80, 0.20],
                k=1
            )[0]

        elif profile == CustomerProfile.SUBSCRIPTION:
            age_days = self.rng.randint(90, 540)
            segment = self.rng.choices(
                [CustomerSegment.CONSUMER_PRO, CustomerSegment.SMB, CustomerSegment.CONSUMER_RETAIL],
                weights=[0.50, 0.30, 0.20],
                k=1
            )[0]
            billing_cycles = age_days // 30
            hist_txns = max(2, min(billing_cycles, 18))
            sampled_rate = self.rng.uniform(0.80, 0.95)
            hist_success = int(round(hist_txns * sampled_rate))
            hist_failure = hist_txns - hist_success
            success_rate = round(hist_success / hist_txns, 4) if hist_txns > 0 else 1.0
            avg_amt = float(self.rng.choice([299.0, 499.0, 799.0, 999.0, 1499.0, 2499.0, 4999.0]))
            pref_method = self.rng.choices(
                [PaymentMethod.CARD, PaymentMethod.UPI, PaymentMethod.NETBANKING],
                weights=[0.55, 0.35, 0.10],
                k=1
            )[0]

        elif profile == CustomerProfile.HIGH_VALUE:
            age_days = self.rng.randint(45, 600)
            segment = self.rng.choices(
                [CustomerSegment.ENTERPRISE, CustomerSegment.SMB, CustomerSegment.CONSUMER_PRO],
                weights=[0.45, 0.40, 0.15],
                k=1
            )[0]
            hist_txns = self.rng.randint(5, 40)
            sampled_rate = self.rng.uniform(0.85, 0.97)
            hist_success = int(round(hist_txns * sampled_rate))
            hist_failure = hist_txns - hist_success
            success_rate = round(hist_success / hist_txns, 4) if hist_txns > 0 else 1.0
            avg_amt = round(self.rng.uniform(12000.0, 125000.0), 2)
            pref_method = self.rng.choices(
                [PaymentMethod.NETBANKING, PaymentMethod.CARD, PaymentMethod.UPI],
                weights=[0.50, 0.40, 0.10],
                k=1
            )[0]
        else:
            raise ValueError(f"Unknown customer profile: {profile}")

        created_dt = base_start - timedelta(days=age_days, seconds=self.rng.randint(0, 86400))
        created_str = created_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        return Customer(
            customer_id=cust_id,
            account_created_at=created_str,
            customer_segment=segment,
            customer_profile=profile,
            customer_age_days=age_days,
            historical_transaction_count=hist_txns,
            historical_success_count=hist_success,
            historical_failure_count=hist_failure,
            historical_success_rate=success_rate,
            average_transaction_amount=avg_amt,
            preferred_payment_method=pref_method,
        )
