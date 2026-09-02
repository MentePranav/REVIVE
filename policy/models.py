"""
Data models for the REVIVE Policy, Safety & Governance Engine.
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from simulator.enums import RecoveryAction


class PolicyDecisionType(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    NO_ACTION = "NO_ACTION"


class PolicyRuleId(str, Enum):
    P001_INVALID_INPUT = "P001_INVALID_INPUT"
    P002_PAYMENT_ALREADY_RESOLVED = "P002_PAYMENT_ALREADY_RESOLVED"
    P003_MAX_AUTOMATED_ATTEMPTS = "P003_MAX_AUTOMATED_ATTEMPTS"
    P004_LOW_DIAGNOSIS_CONFIDENCE = "P004_LOW_DIAGNOSIS_CONFIDENCE"
    P005_HIGH_RISK_GATE = "P005_HIGH_RISK_GATE"
    P006_ACTION_NOT_ALLOWLISTED = "P006_ACTION_NOT_ALLOWLISTED"
    P007_CUSTOMER_CONTACT_LIMIT = "P007_CUSTOMER_CONTACT_LIMIT"
    P008_COOLDOWN_ACTIVE = "P008_COOLDOWN_ACTIVE"
    P009_UNAPPROVED_TEMPLATE = "P009_UNAPPROVED_TEMPLATE"
    P010_ACTION_APPROVED = "P010_ACTION_APPROVED"


class PolicyTraceItem(BaseModel):
    """Audit item recording the validation outcome of an individual policy rule."""
    rule_id: PolicyRuleId
    passed: bool
    description: str


class ExecutionAuthorization(BaseModel):
    """
    Cryptographically isolated authorization token permitting execution.
    Only instantiated when policy evaluation produces ALLOW.
    """
    authorization_id: str
    authorized: bool = True
    payment_id: str
    transaction_id: Optional[str] = None
    customer_id: str
    action: RecoveryAction
    template_id: Optional[str] = None
    policy_version: str
    authorized_at: str


class PolicyDecision(BaseModel):
    """Immutable policy validation result and authorization payload."""
    decision: PolicyDecisionType
    action: RecoveryAction
    event_id: str
    payment_id: str
    customer_id: str
    policy_rule_ids: List[PolicyRuleId] = Field(default_factory=list)
    primary_rule_id: PolicyRuleId
    reason: str
    requires_human_review: bool = False
    policy_version: str
    timestamp: str
    evaluation_trace: List[PolicyTraceItem] = Field(default_factory=list)
    execution_authorization: Optional[ExecutionAuthorization] = None


class PolicyAuditRecord(BaseModel):
    """Machine-readable audit event log entry."""
    audit_id: str
    event_id: str
    payment_id: str
    customer_id: str
    timestamp: str
    recommended_action: str
    final_decision: PolicyDecisionType
    primary_rule_id: PolicyRuleId
    policy_rule_ids: List[str]
    diagnosis_confidence: float
    recoverability_score: float
    risk_signal: str
    attempt_count: int
    policy_version: str
    reason: str
    is_authorized: bool


class PolicyBatchSummary(BaseModel):
    """Aggregated statistics across a batch of policy validations."""
    total_evaluated: int
    allowed_count: int
    denied_count: int
    human_review_count: int
    no_action_count: int
    
    # Block breakdown by rule
    blocked_by_safety_resolved: int
    blocked_by_attempt_cap: int
    blocked_by_confidence_gate: int
    blocked_by_risk_gate: int
    blocked_by_contact_limit: int
    blocked_by_cooldown: int
    blocked_by_allowlist: int
    blocked_by_template_safety: int
    
    policy_version: str
