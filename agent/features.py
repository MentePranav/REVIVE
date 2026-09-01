"""
Feature extraction pipeline for the REVIVE Decision Engine.
Transforms public observable payment events and customer context into normalized feature vectors.
"""

from datetime import datetime
from typing import Optional, Union

from agent.models import NormalizedFailureCategory, ReviveFeatures
from simulator.enums import CustomerProfile, FailureCategory, PaymentMethod, PaymentStatus
from simulator.public_schema import AbandonedCheckout, Customer, Transaction


class FeatureExtractor:
    """Extracts typed, calibrated features from public observable payment and customer telemetry."""

    @classmethod
    def extract_features(
        cls,
        event: Union[Transaction, AbandonedCheckout],
        customer: Optional[Customer]
    ) -> ReviveFeatures:
        is_checkout = isinstance(event, AbandonedCheckout)
        event_id = event.checkout_id if is_checkout else event.transaction_id
        amount = event.amount
        customer_id = event.customer_id

        # 1. Parse Temporal Signals
        try:
            dt = datetime.fromisoformat(event.created_at.replace("Z", "+00:00"))
            day_of_month = dt.day
            hour_of_day = dt.hour
            day_of_week = dt.weekday() # 0 = Monday, 6 = Sunday
        except Exception:
            day_of_month, hour_of_day, day_of_week = 15, 12, 2

        is_salary_window = day_of_month in (1, 2, 3, 4, 5)
        is_month_end_shortage_window = day_of_month in (27, 28, 29, 30, 31)

        # 2. Extract Customer History Context
        if customer:
            hist_txns = customer.historical_transaction_count
            hist_success_rate = customer.historical_success_rate
            hist_failures = customer.historical_failure_count
            cust_age = customer.customer_age_days
            cust_avg_amt = customer.average_transaction_amount
            is_new = (hist_txns <= 2) or (cust_age <= 14) or (customer.customer_profile == CustomerProfile.NEW_CUSTOMER)
            is_sub = customer.customer_profile == CustomerProfile.SUBSCRIPTION
            is_hv = (customer.customer_profile == CustomerProfile.HIGH_VALUE) or (amount >= 25000.0)
            ratio = (amount / max(1.0, cust_avg_amt)) if cust_avg_amt > 0 else 1.0
        else:
            hist_txns = 0
            hist_success_rate = 0.5
            hist_failures = 0
            cust_age = 0
            cust_avg_amt = amount
            is_new = True
            is_sub = False
            is_hv = amount >= 25000.0
            ratio = 1.0

        # 3. Extract Failure Diagnostics & Payment Method
        if is_checkout:
            method_str = event.payment_method_selected.value if event.payment_method_selected else "UNKNOWN"
            method_type_str = "checkout_session"
            attempt_num = 1
            is_abandoned = True
            chk_stage = event.checkout_stage.value
            failure_cat = NormalizedFailureCategory.ABANDONMENT
            err_code = "CHECKOUT_ABANDONED"
            err_source = "customer"
            err_step = "checkout"
            err_reason = "user_abandoned"
        else:
            method_str = event.payment_method.value
            method_type_str = event.payment_method_type.value
            attempt_num = event.attempt_number
            is_abandoned = False
            chk_stage = None

            if event.failure_details:
                f = event.failure_details
                failure_cat = cls._normalize_category(f.failure_category)
                err_code = f.error_code
                err_source = f.error_source.value
                err_step = f.error_step.value
                err_reason = f.error_reason.value
            else:
                failure_cat = NormalizedFailureCategory.UNKNOWN
                err_code, err_source, err_step, err_reason = None, None, None, None

        return ReviveFeatures(
            event_id=event_id,
            customer_id=customer_id,
            amount=amount,
            payment_method=method_str,
            payment_method_type=method_type_str,
            attempt_number=attempt_num,
            is_abandoned=is_abandoned,
            checkout_stage=chk_stage,
            failure_category=failure_cat,
            error_code=err_code,
            error_source=err_source,
            error_step=err_step,
            error_reason=err_reason,
            historical_txns=hist_txns,
            historical_success_rate=hist_success_rate,
            historical_failures=hist_failures,
            customer_age_days=cust_age,
            customer_avg_amount=cust_avg_amt,
            amount_to_avg_ratio=round(ratio, 2),
            is_new_customer=is_new,
            is_subscription=is_sub,
            is_high_value=is_hv,
            day_of_month=day_of_month,
            hour_of_day=hour_of_day,
            day_of_week=day_of_week,
            is_salary_window=is_salary_window,
            is_month_end_shortage_window=is_month_end_shortage_window
        )

    @classmethod
    def _normalize_category(cls, cat: FailureCategory) -> NormalizedFailureCategory:
        mapping = {
            FailureCategory.TRANSIENT_GATEWAY_FAILURE: NormalizedFailureCategory.TRANSIENT,
            FailureCategory.BANK_DECLINE: NormalizedFailureCategory.BANK_DECLINE,
            FailureCategory.INSUFFICIENT_FUNDS: NormalizedFailureCategory.INSUFFICIENT_FUNDS,
            FailureCategory.AUTHENTICATION_FAILURE: NormalizedFailureCategory.AUTHENTICATION,
            FailureCategory.PAYMENT_METHOD_FAILURE: NormalizedFailureCategory.PAYMENT_METHOD,
            FailureCategory.USER_ABANDONMENT: NormalizedFailureCategory.ABANDONMENT,
            FailureCategory.HARD_FAILURE: NormalizedFailureCategory.HARD_FAILURE,
            FailureCategory.HIGH_RISK: NormalizedFailureCategory.HIGH_RISK,
        }
        return mapping.get(cat, NormalizedFailureCategory.UNKNOWN)
