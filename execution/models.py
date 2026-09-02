"""
Pydantic data models for REVIVE Controlled Recovery Execution Simulator.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agent.models import ReviveRecommendation
from policy.models import PolicyDecision
from simulator.enums import RecoveryAction


class ExecutionStatus(str, Enum):
    EXECUTED = "EXECUTED"
    NO_ACTION_TAKEN = "NO_ACTION_TAKEN"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"
    DUPLICATE = "DUPLICATE"
    FAILED = "FAILED"


class SimulatedRecoveryOutcome(str, Enum):
    RECOVERED = "RECOVERED"
    NOT_RECOVERED = "NOT_RECOVERED"
    NATURAL_RECOVERY = "NATURAL_RECOVERY"
    PENDING = "PENDING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AuditEventType(str, Enum):
    REQUESTED = "REQUESTED"
    AUTHORIZATION_VALIDATED = "AUTHORIZATION_VALIDATED"
    EXECUTED = "EXECUTED"
    BLOCKED = "BLOCKED"
    DUPLICATE = "DUPLICATE"
    OUTCOME_RECORDED = "OUTCOME_RECORDED"


class ExecutionAuditEvent(BaseModel):
    """Immutable audit trail event recording an execution step."""
    audit_id: str
    event_type: AuditEventType
    payment_id: str
    transaction_id: Optional[str] = None
    customer_id: str
    action: RecoveryAction
    timestamp: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    """Strongly typed output of a controlled simulated recovery execution."""
    execution_id: str
    execution_key: str = Field(..., description="Deterministic idempotency key")
    authorization_id: Optional[str] = None
    transaction_id: Optional[str] = None
    payment_id: str
    customer_id: str
    authorized_action: RecoveryAction
    execution_status: ExecutionStatus
    execution_reason: str
    executed_at: str
    attempt_number: int = 1
    customer_contact_attempt_number: int = 0
    simulated_external_reference: Optional[str] = None
    recovery_outcome: SimulatedRecoveryOutcome = SimulatedRecoveryOutcome.NOT_APPLICABLE
    recovered_amount: float = 0.0
    audit_event_id: str
    policy_version: str
    executor_version: str = "1.0.0"


class ExecutionLifecycleTrace(BaseModel):
    """Complete end-to-end trace from raw payment failure to outcome for audit and demonstration."""
    event_id: str
    payment_id: str
    customer_id: str
    recommendation: ReviveRecommendation
    policy_decision: PolicyDecision
    execution_result: ExecutionResult
    audit_events: List[ExecutionAuditEvent] = Field(default_factory=list)


class ActionExecutionStats(BaseModel):
    """Action-level performance and recovery statistics."""
    action: str
    recommended_count: int = 0
    authorized_count: int = 0
    executed_count: int = 0
    blocked_count: int = 0
    recovered_count: int = 0
    recovered_revenue: float = 0.0
    recovery_rate: float = 0.0
    intervention_success_rate: float = 0.0


class BatchExecutionSummary(BaseModel):
    """Aggregated financial, operational, and safety metrics for a batch execution."""
    total_transactions: int
    total_failed_opportunities: int
    recommendations_count: int
    
    # Policy Decisions
    policy_authorized_count: int
    policy_human_review_count: int
    policy_denied_count: int
    policy_no_action_count: int
    
    # Execution Outcomes
    actions_executed_count: int
    actions_blocked_count: int
    duplicate_attempts_prevented: int
    successful_recoveries: int
    
    # Financials (in INR)
    total_revenue_at_risk: float
    natural_recovery_revenue: float
    total_recovered_revenue: float
    incremental_recovered_revenue: float
    
    # Rates
    overall_recovery_rate: float
    intervention_success_rate: float
    
    # Breakdowns
    action_breakdown: Dict[str, ActionExecutionStats]
    safety_metrics: Dict[str, int]
    
    executor_version: str = "1.0.0"
