"""
Evaluation-Only Ground Truth schemas for the REVIVE payment simulator.
CRITICAL: These records are strictly reserved for post-hoc evaluation and benchmarking.
They must NEVER be exposed to agent inference pipelines.
"""

from typing import Dict
from pydantic import BaseModel, Field

from simulator.enums import RecoveryAction, RecoveryOutcome


class GroundTruthRecord(BaseModel):
    """
    Hidden ground truth associated with an eligible failed transaction or abandoned checkout.
    Establishes the objective benchmark against which recovery strategies are evaluated.
    """
    event_id: str = Field(..., description="Transaction ID or Checkout ID")
    customer_id: str = Field(..., min_length=4)
    ground_truth_recoverable: bool = Field(..., description="True if revenue was inherently recoverable")
    ground_truth_best_action: RecoveryAction = Field(..., description="Optimal synthetic intervention")
    ground_truth_recovery_probability: float = Field(..., ge=0.0, le=1.0, description="Inherent recovery likelihood")
    ground_truth_customer_friction: float = Field(..., ge=0.0, le=1.0, description="Risk of customer annoyance/churn")
    counterfactual_outcomes: Dict[str, str] = Field(
        ...,
        description="Outcome of applying each candidate RecoveryAction (e.g. {'RETRY': 'SUCCESS', 'PAYMENT_LINK': 'SUCCESS', ...})"
    )
    causal_explanation: str = Field(..., description="Underlying domain reason for the recovery characteristics")
    is_already_resolved: bool = Field(default=False, description="True if customer recovered organically without intervention")
