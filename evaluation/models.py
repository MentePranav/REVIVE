"""
Data structures and schema definitions for the REVIVE Evaluation Engine.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from simulator.enums import RecoveryAction, RecoveryOutcome


class StrategyDecision(BaseModel):
    """Structured decision output produced by any recovery strategy."""
    strategy_name: str = Field(..., description="Identifier of strategy that made the decision")
    event_id: str = Field(..., description="Transaction ID or Checkout ID")
    customer_id: str = Field(..., min_length=4)
    action: RecoveryAction = Field(..., description="Chosen recovery intervention")
    rule_id: Optional[str] = Field(default=None, description="Explicit rule identifier that triggered action")
    reason: str = Field(..., description="Domain rationale for chosen action")
    timestamp: str = Field(..., description="Timestamp when decision was made")
    eligible: bool = Field(default=True, description="Whether event was eligible for intervention")
    attempt_number: int = Field(default=1, ge=1)


class ActionCostConfig(BaseModel):
    """Configurable synthetic execution costs per action type (in INR)."""
    costs: Dict[str, float] = Field(default_factory=lambda: {
        RecoveryAction.RETRY.value: 2.0,         # Processor retry fee / gateway surcharge
        RecoveryAction.REMINDER.value: 1.5,      # SMS/WhatsApp notification unit cost
        RecoveryAction.PAYMENT_LINK.value: 3.0,  # Link generation & multi-channel notification cost
        RecoveryAction.HUMAN_REVIEW.value: 50.0, # Human operator triage time
        RecoveryAction.DO_NOTHING.value: 0.0,    # Zero intervention cost
    })

    def get_cost(self, action: RecoveryAction) -> float:
        return self.costs.get(action.value, 0.0)


class EvaluationOutcomeRecord(BaseModel):
    """Detailed record of an individual intervention decision, simulated resolution, and financial yield."""
    decision: StrategyDecision
    amount: float = Field(..., ge=0.0)
    simulated_outcome: RecoveryOutcome
    recovered_amount: float = Field(..., ge=0.0)
    action_cost: float = Field(..., ge=0.0)
    is_recovered: bool = Field(..., description="True if revenue was captured via intervention or natural resolution")
    is_incremental: bool = Field(..., description="True if recovery was directly caused by the strategy intervention")
    is_false_positive: bool = Field(..., description="True if an intervention was attempted on a non-recoverable scenario")


class EvaluationMetrics(BaseModel):
    """Aggregated performance metrics for a single evaluated strategy."""
    strategy_name: str
    total_transactions_evaluated: int
    failed_transactions_considered: int
    abandoned_checkouts_considered: int
    total_eligible_opportunities: int
    total_interventions_attempted: int
    successful_recoveries: int
    recovered_revenue: float
    revenue_at_risk: float
    natural_recovery_revenue: float
    incremental_revenue: float
    intervention_precision: float
    recoverable_opportunity_capture_rate: float
    false_positive_rate: float
    total_action_costs: float
    net_incremental_value: float


class BenchmarkComparison(BaseModel):
    """Comparative benchmarking matrix across multiple recovery strategies."""
    dataset_path: str
    evaluated_at: str
    strategy_metrics: Dict[str, EvaluationMetrics]
