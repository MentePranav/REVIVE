"""
Public / Model-Visible schemas for the REVIVE payment simulator.
These schemas represent data visible to payment operators and AI inference engines.
CRITICAL: Ground truth evaluation fields are strictly prohibited from this module.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

from simulator.enums import (
    CustomerProfile,
    CustomerSegment,
    PaymentMethod,
    PaymentMethodType,
    PaymentStatus,
    ErrorSource,
    ErrorStep,
    ErrorReason,
    FailureCategory,
    CheckoutStage,
)


class PaymentFailureDetails(BaseModel):
    """Diagnostic failure attributes matching gateway / webhook payloads."""
    error_code: str = Field(..., description="Machine-readable error identifier")
    error_description: str = Field(..., description="Human-readable failure explanation")
    error_source: ErrorSource = Field(..., description="Entity where failure originated")
    error_step: ErrorStep = Field(..., description="Lifecycle step where execution halted")
    error_reason: ErrorReason = Field(..., description="Normalized cause of failure")
    failure_category: FailureCategory = Field(..., description="High-level category for diagnosis")


class PaymentAttempt(BaseModel):
    """Subsequent or preceding payment attempt under the same payment/order."""
    attempt_number: int = Field(..., ge=1)
    attempted_at: str
    status: PaymentStatus
    failure_details: Optional[PaymentFailureDetails] = None


class Customer(BaseModel):
    """Customer profile and aggregated historical timeline attributes."""
    customer_id: str = Field(..., min_length=4)
    account_created_at: str
    customer_segment: CustomerSegment
    customer_profile: CustomerProfile
    customer_age_days: int = Field(..., ge=0)
    historical_transaction_count: int = Field(..., ge=0)
    historical_success_count: int = Field(..., ge=0)
    historical_failure_count: int = Field(..., ge=0)
    historical_success_rate: float = Field(..., ge=0.0, le=1.0)
    average_transaction_amount: float = Field(..., ge=0.0)
    preferred_payment_method: PaymentMethod

    @field_validator("historical_success_rate")
    @classmethod
    def validate_rate(cls, v: float) -> float:
        return round(v, 4)


class Transaction(BaseModel):
    """Transaction record representing an individual payment event."""
    transaction_id: str = Field(..., min_length=4)
    payment_id: str = Field(..., min_length=4)
    order_id: str = Field(..., min_length=4)
    customer_id: str = Field(..., min_length=4)
    created_at: str
    amount: float = Field(..., gt=0.0, description="Amount in INR, must be strictly positive")
    currency: str = Field(default="INR")
    payment_method: PaymentMethod
    payment_method_type: PaymentMethodType
    status: PaymentStatus
    attempt_number: int = Field(default=1, ge=1)
    is_abandoned: bool = Field(default=False)
    failure_details: Optional[PaymentFailureDetails] = None
    is_late_success: bool = Field(default=False, description="Whether transaction organically succeeded later")
    late_success_at: Optional[str] = None


class AbandonedCheckout(BaseModel):
    """Checkout session abandoned prior to payment authorization."""
    checkout_id: str = Field(..., min_length=4)
    customer_id: str = Field(..., min_length=4)
    created_at: str
    amount: float = Field(..., gt=0.0)
    currency: str = Field(default="INR")
    payment_method_selected: Optional[PaymentMethod] = None
    checkout_stage: CheckoutStage
    time_spent_seconds: int = Field(..., ge=0)
    is_abandoned: bool = Field(default=True)
