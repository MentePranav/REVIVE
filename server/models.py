"""
Pydantic API schemas for the REVIVE Interactive Control Center.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    seed: int = Field(default=42, ge=0, le=2147483647)
    size: int = Field(default=100, ge=1, le=10000)
    scenario: str = Field(default="balanced", max_length=50)


class ActionMixStat(BaseModel):
    action: str
    recommended_count: int
    authorized_count: int
    executed_count: int
    recovered_count: int
    recovered_revenue: float
    recovery_rate: float
    intervention_success_rate: float


class SimulationSummaryResponse(BaseModel):
    total_transactions: int
    total_failed_opportunities: int
    revenue_at_risk: float
    natural_recovery_revenue: float
    total_recovered_revenue: float
    incremental_recovered_revenue: float
    overall_recovery_rate: float
    intervention_success_rate: float
    policy_authorized_count: int
    policy_human_review_count: int
    policy_denied_count: int
    policy_no_action_count: int
    actions_executed_count: int
    actions_blocked_count: int
    duplicate_attempts_prevented: int
    action_breakdown: Dict[str, ActionMixStat]
    safety_metrics: Dict[str, int]
    session_seed: int
    scenario: str
    disclaimer: str = "SYNTHETIC EVALUATION — Controlled simulation benchmark for hackathon prototype."


class RecoveryCaseListItem(BaseModel):
    event_id: str
    payment_id: str
    customer_id: str
    amount: float
    failure_category: str
    error_reason: Optional[str] = None
    diagnosis: str
    confidence: float
    recoverability_score: float
    recoverability_tier: str
    recommended_action: str
    policy_decision: str
    primary_rule_id: Optional[str] = None
    execution_status: str
    recovery_outcome: str
    recovered_amount: float
    has_authorization: bool
    created_at: str


class ActionScoreItem(BaseModel):
    action: str
    success_probability: float
    expected_revenue: float
    action_cost: float
    friction_penalty: float
    expected_value: float


class SafetyCheckItem(BaseModel):
    rule_id: str
    rule_name: str
    passed: bool
    description: str


class RecoveryCaseDetailResponse(BaseModel):
    event_id: str
    payment_id: str
    customer_id: str
    amount: float
    currency: str
    payment_method: str
    payment_method_type: str
    created_at: str
    failure_category: str
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    
    # Phase 4 Intelligence
    diagnosis: str
    diagnosis_confidence: float
    diagnosis_risk_signal: str
    diagnosis_reason_codes: List[str]
    diagnosis_explanation: str
    recoverability_score: float
    recoverability_tier: str
    recommended_action: str
    action_scores: List[ActionScoreItem]
    top_positive_factors: List[str]
    feature_contributions: Dict[str, float]
    
    # Phase 5 Policy Governance
    policy_decision: str
    policy_rule_id: Optional[str] = None
    policy_reason: str
    safety_checklist: List[SafetyCheckItem]
    authorization_id: Optional[str] = None
    authorization_timestamp: Optional[str] = None
    can_execute: bool
    
    # Phase 6 Execution & Outcome
    execution_status: str
    execution_reason: str
    simulated_external_reference: Optional[str] = None
    recovery_outcome: str
    recovered_amount: float
    attempt_number: int
    customer_contact_attempt_number: int
    audit_events: List[Dict[str, Any]]


class ExecuteRecoveryRequest(BaseModel):
    event_id: str


class ExecuteRecoveryResponse(BaseModel):
    success: bool
    execution_status: str
    recovery_outcome: str
    recovered_amount: float
    message: str
    external_reference: Optional[str] = None
    audit_event_id: Optional[str] = None
    authorization_id: Optional[str] = None


class SafetyDashboardResponse(BaseModel):
    total_checks: int
    policy_allows: int
    policy_denies: int
    human_reviews: int
    policy_no_actions: int
    blocks_breakdown: Dict[str, int]
    rule_distributions: Dict[str, int]
    disclaimer: str = "SYNTHETIC EVALUATION — Controlled simulation benchmark."


class AuditLogItem(BaseModel):
    audit_id: str
    timestamp: str
    event_type: str
    payment_id: str
    transaction_id: Optional[str] = None
    customer_id: str
    action: str
    details: Dict[str, Any]


class BenchmarkResponse(BaseModel):
    evaluated_at: str
    dataset_info: str
    strategies: Dict[str, Any]
    summary_markdown: Optional[str] = None
