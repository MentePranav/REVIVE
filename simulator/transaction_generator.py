"""
Chronological transaction generation engine with correlated failure semantics.
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from simulator.config import SimulatorConfig
from simulator.enums import (
    CustomerProfile,
    PaymentMethod,
    PaymentMethodType,
    PaymentStatus,
    ErrorSource,
    ErrorStep,
    ErrorReason,
    FailureCategory,
)
from simulator.public_schema import Customer, Transaction, PaymentFailureDetails


class TransactionGenerator:
    """Generates chronologically ordered, realistic transaction streams per customer."""

    def __init__(self, config: SimulatorConfig, rng: random.Random):
        self.config = config
        self.rng = rng

    def generate_transactions(
        self,
        customers: List[Customer],
        target_transaction_count: int | None = None
    ) -> List[Transaction]:
        target_count = target_transaction_count or self.config.transaction_count
        base_start = datetime.fromisoformat(self.config.start_date.replace("Z", "+00:00"))
        sim_duration = timedelta(days=self.config.simulation_days)

        all_transactions: List[Transaction] = []
        global_txn_counter = 0

        # Estimate average transactions per customer
        cust_count = len(customers)
        base_txns_per_cust = max(1, target_count // cust_count)

        for customer in customers:
            # Determine number of transactions for this customer during simulation
            num_txns = self._get_num_transactions_for_profile(customer.customer_profile, base_txns_per_cust)
            if num_txns <= 0:
                num_txns = 1

            cust_txns = self._generate_customer_timeline(
                customer=customer,
                count=num_txns,
                start_time=base_start,
                duration=sim_duration,
                start_id=global_txn_counter + 1
            )
            global_txn_counter += len(cust_txns)
            all_transactions.extend(cust_txns)

        # If we need exact target_count adjustment
        if len(all_transactions) > target_count:
            # Deterministically trim from end while preserving chronological customer subsets
            all_transactions = all_transactions[:target_count]
        elif len(all_transactions) < target_count:
            diff = target_count - len(all_transactions)
            # Add extra transactions to high-activity customers
            active_customers = [c for c in customers if c.customer_profile in (CustomerProfile.RELIABLE, CustomerProfile.SUBSCRIPTION, CustomerProfile.HIGH_VALUE)]
            if not active_customers:
                active_customers = customers

            for i in range(diff):
                cust = self.rng.choice(active_customers)
                global_txn_counter += 1
                last_time = base_start + timedelta(seconds=self.rng.randint(0, int(sim_duration.total_seconds())))
                txn = self._create_single_transaction(
                    txn_num=global_txn_counter,
                    customer=cust,
                    timestamp=last_time,
                    attempt_num=1
                )
                all_transactions.append(txn)

        # Sort all transactions chronologically
        all_transactions.sort(key=lambda t: t.created_at)
        return all_transactions

    def _get_num_transactions_for_profile(self, profile: CustomerProfile, base: int) -> int:
        if profile == CustomerProfile.SUBSCRIPTION:
            # Fixed monthly cadence in 90 days = ~3 transactions
            return max(1, self.config.simulation_days // 30)
        elif profile == CustomerProfile.RELIABLE:
            return max(2, self.rng.randint(base, base * 3 + 2))
        elif profile == CustomerProfile.HIGH_VALUE:
            return max(1, self.rng.randint(1, base + 2))
        elif profile == CustomerProfile.OCCASIONAL_FAILURE:
            return max(1, self.rng.randint(1, base * 2 + 1))
        elif profile == CustomerProfile.HIGH_FAILURE:
            return max(1, self.rng.randint(1, base + 3))
        elif profile == CustomerProfile.NEW_CUSTOMER:
            return self.rng.choices([1, 2, 3], weights=[0.60, 0.30, 0.10], k=1)[0]
        return base

    def _generate_customer_timeline(
        self,
        customer: Customer,
        count: int,
        start_time: datetime,
        duration: timedelta,
        start_id: int
    ) -> List[Transaction]:
        txns: List[Transaction] = []
        profile = customer.customer_profile

        # Account creation timestamp
        cust_created = datetime.fromisoformat(customer.account_created_at.replace("Z", "+00:00"))
        effective_start = max(start_time, cust_created)
        remaining_seconds = max(3600, int((start_time + duration - effective_start).total_seconds()))

        current_time = effective_start + timedelta(seconds=self.rng.randint(0, min(86400 * 5, remaining_seconds // (count + 1))))

        for idx in range(count):
            txn_id_num = start_id + idx
            txn = self._create_single_transaction(
                txn_num=txn_id_num,
                customer=customer,
                timestamp=current_time,
                attempt_num=1
            )
            txns.append(txn)

            # Advance time for next transaction
            if profile == CustomerProfile.SUBSCRIPTION:
                # Regular 30 day interval with minor jitter (+/- 2 hours)
                interval_secs = (30 * 86400) + self.rng.randint(-7200, 7200)
            elif profile == CustomerProfile.NEW_CUSTOMER:
                interval_secs = self.rng.randint(86400 * 2, 86400 * 10)
            elif profile == CustomerProfile.HIGH_FAILURE:
                # Clustered retries/attempts
                interval_secs = self.rng.randint(3600 * 4, 86400 * 7)
            else:
                interval_secs = self.rng.randint(86400 * 3, 86400 * 25)

            current_time = current_time + timedelta(seconds=interval_secs)
            if current_time > (start_time + duration):
                # Clamp within simulation horizon with slight time offset
                current_time = start_time + duration - timedelta(seconds=self.rng.randint(60, 3600))

        return txns

    def _create_single_transaction(
        self,
        txn_num: int,
        customer: Customer,
        timestamp: datetime,
        attempt_num: int = 1
    ) -> Transaction:
        txn_id = f"txn_{txn_num:08d}"
        pay_id = f"pay_{txn_num:08d}"
        order_id = f"order_{txn_num:08d}"

        # Determine Amount
        amount = self._sample_amount(customer)

        # Determine Payment Method
        method, method_type = self._sample_payment_method(customer)

        # Determine Status
        status, failure_details, is_late_success, late_time_str = self._determine_outcome(customer, method, timestamp)

        return Transaction(
            transaction_id=txn_id,
            payment_id=pay_id,
            order_id=order_id,
            customer_id=customer.customer_id,
            created_at=timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            amount=amount,
            currency="INR",
            payment_method=method,
            payment_method_type=method_type,
            status=status,
            attempt_number=attempt_num,
            is_abandoned=False,
            failure_details=failure_details,
            is_late_success=is_late_success,
            late_success_at=late_time_str
        )

    def _sample_amount(self, customer: Customer) -> float:
        profile = customer.customer_profile
        if profile == CustomerProfile.SUBSCRIPTION:
            return customer.average_transaction_amount
        elif profile == CustomerProfile.HIGH_VALUE:
            # High value distribution: ₹10,000 - ₹1,80,000
            val = self.rng.lognormvariate(10.2, 0.6)
            return round(max(9999.0, min(val, 250000.0)), 2)
        elif profile == CustomerProfile.NEW_CUSTOMER:
            val = self.rng.lognormvariate(6.5, 0.8)
            return round(max(49.0, min(val, 2999.0)), 2)
        else:
            # Standard lognormal distribution with mean around ₹800-₹1500
            val = self.rng.lognormvariate(6.8, 0.9)
            return round(max(49.0, min(val, 25000.0)), 2)

    def _sample_payment_method(self, customer: Customer) -> Tuple[PaymentMethod, PaymentMethodType]:
        # Preference biased towards customer preferred method (70% weight)
        pref = customer.preferred_payment_method
        all_methods = [PaymentMethod.UPI, PaymentMethod.CARD, PaymentMethod.NETBANKING, PaymentMethod.WALLET]
        weights = [0.70 if m == pref else 0.10 for m in all_methods]

        chosen_method = self.rng.choices(all_methods, weights=weights, k=1)[0]

        if chosen_method == PaymentMethod.UPI:
            m_type = self.rng.choices([PaymentMethodType.UPI_INTENT, PaymentMethodType.UPI_COLLECT], weights=[0.75, 0.25], k=1)[0]
        elif chosen_method == PaymentMethod.CARD:
            m_type = self.rng.choices([PaymentMethodType.DEBIT_CARD, PaymentMethodType.CREDIT_CARD], weights=[0.55, 0.45], k=1)[0]
        elif chosen_method == PaymentMethod.NETBANKING:
            if customer.customer_profile == CustomerProfile.HIGH_VALUE:
                m_type = PaymentMethodType.NETBANKING_CORP
            else:
                m_type = PaymentMethodType.NETBANKING_RETAIL
        elif chosen_method == PaymentMethod.WALLET:
            m_type = PaymentMethodType.PREPAID_WALLET
        else:
            m_type = PaymentMethodType.UPI_INTENT

        return chosen_method, m_type

    def _determine_outcome(
        self,
        customer: Customer,
        method: PaymentMethod,
        timestamp: datetime
    ) -> Tuple[PaymentStatus, Optional[PaymentFailureDetails], bool, Optional[str]]:
        profile = customer.customer_profile
        fail_prob = 1.0 - customer.historical_success_rate

        # Temporal effects: e.g. end of month (27th-31st) has higher insufficient funds
        day_of_month = timestamp.day
        if day_of_month in (27, 28, 29, 30, 31):
            fail_prob = min(0.90, fail_prob * 1.35)
        elif day_of_month in (1, 2, 3, 4, 5):
            fail_prob = max(0.02, fail_prob * 0.70)

        # Roll for success vs failure
        if self.rng.random() > fail_prob:
            return PaymentStatus.SUCCESS, None, False, None

        # Payment failed - pick correlated failure category
        failure_category = self._pick_failure_category(customer, method, day_of_month)
        failure_details = self._build_failure_details(failure_category, method)

        # Edge case: Late success (~4% of failed payments organically succeed later)
        is_late_success = False
        late_time_str = None
        if failure_category in (FailureCategory.TRANSIENT_GATEWAY_FAILURE, FailureCategory.BANK_DECLINE) and self.rng.random() < 0.05:
            is_late_success = True
            delay_minutes = self.rng.randint(15, 180)
            late_time = timestamp + timedelta(minutes=delay_minutes)
            late_time_str = late_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        return PaymentStatus.FAILED, failure_details, is_late_success, late_time_str

    def _pick_failure_category(
        self,
        customer: Customer,
        method: PaymentMethod,
        day_of_month: int
    ) -> FailureCategory:
        profile = customer.customer_profile

        if profile == CustomerProfile.RELIABLE:
            # Mostly transient gateway timeouts or occasional auth OTP typo
            return self.rng.choices(
                [
                    FailureCategory.TRANSIENT_GATEWAY_FAILURE,
                    FailureCategory.AUTHENTICATION_FAILURE,
                    FailureCategory.BANK_DECLINE,
                    FailureCategory.PAYMENT_METHOD_FAILURE
                ],
                weights=[0.60, 0.25, 0.10, 0.05],
                k=1
            )[0]

        elif profile == CustomerProfile.HIGH_FAILURE:
            # Heavy insufficient funds, bank declines, repeated method failures
            return self.rng.choices(
                [
                    FailureCategory.INSUFFICIENT_FUNDS,
                    FailureCategory.BANK_DECLINE,
                    FailureCategory.PAYMENT_METHOD_FAILURE,
                    FailureCategory.HARD_FAILURE,
                    FailureCategory.TRANSIENT_GATEWAY_FAILURE
                ],
                weights=[0.45, 0.25, 0.15, 0.10, 0.05],
                k=1
            )[0]

        elif profile == CustomerProfile.SUBSCRIPTION:
            # Mandate failures, card expiry, insufficient balance
            return self.rng.choices(
                [
                    FailureCategory.PAYMENT_METHOD_FAILURE,
                    FailureCategory.INSUFFICIENT_FUNDS,
                    FailureCategory.BANK_DECLINE,
                    FailureCategory.TRANSIENT_GATEWAY_FAILURE
                ],
                weights=[0.40, 0.30, 0.20, 0.10],
                k=1
            )[0]

        elif profile == CustomerProfile.HIGH_VALUE:
            # Bank authorization limits, corporate gateway timeouts, high risk flags
            return self.rng.choices(
                [
                    FailureCategory.BANK_DECLINE,
                    FailureCategory.TRANSIENT_GATEWAY_FAILURE,
                    FailureCategory.HIGH_RISK,
                    FailureCategory.AUTHENTICATION_FAILURE
                ],
                weights=[0.40, 0.35, 0.15, 0.10],
                k=1
            )[0]

        # Default weighted distribution
        categories = list(self.config.failure_weights.keys())
        weights = [self.config.failure_weights[c] for c in categories]
        chosen_cat_str = self.rng.choices(categories, weights=weights, k=1)[0]
        return FailureCategory(chosen_cat_str)

    def _build_failure_details(
        self,
        category: FailureCategory,
        method: PaymentMethod
    ) -> PaymentFailureDetails:
        if category == FailureCategory.TRANSIENT_GATEWAY_FAILURE:
            return PaymentFailureDetails(
                error_code="GATEWAY_ERROR_TIMEOUT",
                error_description="The payment gateway timed out while communicating with the processor.",
                error_source=ErrorSource.GATEWAY,
                error_step=ErrorStep.PAYMENT_PROCESSING,
                error_reason=ErrorReason.TIMEOUT,
                failure_category=category
            )

        elif category == FailureCategory.BANK_DECLINE:
            return PaymentFailureDetails(
                error_code="BAD_REQUEST_PAYMENT_DECLINED_BY_BANK",
                error_description="The issuing bank declined authorization for this transaction.",
                error_source=ErrorSource.BANK,
                error_step=ErrorStep.PAYMENT_AUTHORIZATION,
                error_reason=ErrorReason.PAYMENT_FAILED,
                failure_category=category
            )

        elif category == FailureCategory.INSUFFICIENT_FUNDS:
            return PaymentFailureDetails(
                error_code="BAD_REQUEST_PAYMENT_ACCOUNT_INSUFFICIENT_BALANCE",
                error_description="The bank account or card balance was insufficient to complete the transaction.",
                error_source=ErrorSource.CUSTOMER,
                error_step=ErrorStep.PAYMENT_AUTHORIZATION,
                error_reason=ErrorReason.INSUFFICIENT_FUNDS,
                failure_category=category
            )

        elif category == FailureCategory.AUTHENTICATION_FAILURE:
            return PaymentFailureDetails(
                error_code="BAD_REQUEST_PAYMENT_OTP_INCORRECT",
                error_description="Customer entered an incorrect OTP or 3D-Secure authentication expired.",
                error_source=ErrorSource.CUSTOMER,
                error_step=ErrorStep.PAYMENT_AUTHENTICATION,
                error_reason=ErrorReason.AUTHENTICATION_FAILED,
                failure_category=category
            )

        elif category == FailureCategory.PAYMENT_METHOD_FAILURE:
            desc = "UPI VPA is inactive or invalid." if method == PaymentMethod.UPI else "Payment card is expired or inactive."
            code = "UPI_VPA_INACTIVE" if method == PaymentMethod.UPI else "BAD_REQUEST_PAYMENT_CARD_EXPIRED"
            return PaymentFailureDetails(
                error_code=code,
                error_description=desc,
                error_source=ErrorSource.CUSTOMER,
                error_step=ErrorStep.PAYMENT_PROCESSING,
                error_reason=ErrorReason.PAYMENT_METHOD_FAILED,
                failure_category=category
            )

        elif category == FailureCategory.USER_ABANDONMENT:
            return PaymentFailureDetails(
                error_code="BAD_REQUEST_PAYMENT_CANCELLED_BY_USER",
                error_description="The payment was explicitly cancelled by the customer.",
                error_source=ErrorSource.CUSTOMER,
                error_step=ErrorStep.CHECKOUT,
                error_reason=ErrorReason.USER_ABANDONED,
                failure_category=category
            )

        elif category == FailureCategory.HARD_FAILURE:
            return PaymentFailureDetails(
                error_code="CARD_RESTRICTED_OR_BLOCKED",
                error_description="The instrument or account is permanently blocked by the issuer.",
                error_source=ErrorSource.BANK,
                error_step=ErrorStep.PAYMENT_PROCESSING,
                error_reason=ErrorReason.PAYMENT_FAILED,
                failure_category=category
            )

        elif category == FailureCategory.HIGH_RISK:
            return PaymentFailureDetails(
                error_code="GATEWAY_FRAUD_RISK_BLOCK",
                error_description="Transaction rejected by automated risk policy due to abnormal velocity.",
                error_source=ErrorSource.INTERNAL,
                error_step=ErrorStep.PAYMENT_PROCESSING,
                error_reason=ErrorReason.RISK_DETECTED,
                failure_category=category
            )

        raise ValueError(f"Unknown failure category: {category}")
