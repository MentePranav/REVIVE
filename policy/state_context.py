"""
Payment and Customer state tracking context for policy validation.
"""

from typing import Optional
from pydantic import BaseModel, Field
from simulator.enums import PaymentStatus, RecoveryAction


class PaymentStateContext(BaseModel):
    """Real-time lifecycle state and attempt history for a specific payment."""
    payment_id: str
    transaction_id: Optional[str] = None
    customer_id: str
    current_status: PaymentStatus = PaymentStatus.FAILED
    is_already_resolved: bool = False
    automated_attempt_count: int = Field(default=0, ge=0)
    retry_attempt_count: int = Field(default=0, ge=0)
    last_action_timestamp: Optional[str] = None
    last_action_type: Optional[RecoveryAction] = None


class CustomerStateContext(BaseModel):
    """Customer-level communication and fatigue tracking context."""
    customer_id: str
    contact_actions_count: int = Field(default=0, ge=0, description="Total reminders or payment links delivered")
    last_contact_timestamp: Optional[str] = None
