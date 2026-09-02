"""
Centralized Configuration and Template Registry for REVIVE Policy & Governance Engine.
"""

from typing import List, Set
from pydantic import BaseModel, Field

from simulator.enums import RecoveryAction


class ApprovedTemplateRegistry:
    """Registry of pre-approved, verified customer communication templates."""
    REMINDER_STANDARD_V1 = "REMINDER_STANDARD_V1"
    PAYMENT_LINK_STANDARD_V1 = "PAYMENT_LINK_STANDARD_V1"
    CHECKOUT_RECOVERY_V1 = "CHECKOUT_RECOVERY_V1"

    @classmethod
    def all_templates(cls) -> Set[str]:
        return {
            cls.REMINDER_STANDARD_V1,
            cls.PAYMENT_LINK_STANDARD_V1,
            cls.CHECKOUT_RECOVERY_V1,
        }

    @classmethod
    def get_template_for_action(cls, action: RecoveryAction, is_checkout: bool = False) -> str:
        if is_checkout:
            return cls.CHECKOUT_RECOVERY_V1
        if action == RecoveryAction.REMINDER:
            return cls.REMINDER_STANDARD_V1
        if action == RecoveryAction.PAYMENT_LINK:
            return cls.PAYMENT_LINK_STANDARD_V1
        return ""


class PolicyConfig(BaseModel):
    """Centralized policy and safety parameters."""
    policy_version: str = "1.0.0"
    
    # Confidence & Recoverability Gates
    minimum_diagnosis_confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    minimum_recoverability_for_automation: float = Field(default=0.30, ge=0.0, le=1.0)
    
    # Hard Attempt Caps
    max_retry_attempts: int = Field(default=2, ge=1, le=3)
    max_automated_actions_per_payment: int = Field(default=2, ge=1, le=3)
    max_customer_contact_actions: int = Field(default=2, ge=1, le=5)
    
    # Temporal Cooldowns
    minimum_action_cooldown_seconds: int = Field(default=300, ge=0, description="5 minute minimum cooldown between interventions")
    
    # Safety Gates
    high_risk_requires_human: bool = True
    reject_unresolved_payments_only: bool = True
    
    # Allowlists
    allowed_actions: List[str] = Field(
        default_factory=lambda: [
            RecoveryAction.DO_NOTHING.value,
            RecoveryAction.RETRY.value,
            RecoveryAction.REMINDER.value,
            RecoveryAction.PAYMENT_LINK.value,
            RecoveryAction.HUMAN_REVIEW.value,
        ]
    )
    
    approved_templates: List[str] = Field(
        default_factory=lambda: list(ApprovedTemplateRegistry.all_templates())
    )
