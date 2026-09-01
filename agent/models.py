"""
Pydantic data models for the REVIVE Diagnosis & Recovery Scoring Engine.
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from simulator.enums import RecoveryAction


class NormalizedFailureCategory(str, Enum):
    TRANSIENT = "TRANSIENT"
    BANK_DECLINE = "BANK_DECLINE"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    AUTHENTICATION = "AUTHENTICATION"
    PAYMENT_METHOD = "PAYMENT_METHOD"
    ABANDONMENT = "ABANDONMENT"
    HARD_FAILURE = "HARD_FAILURE"
    HIGH_RISK = "HIGH_RISK"
    UNKNOWN = "UNKNOWN"


class RiskSignal(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class RecoverabilityTier(str, Enum):
    HIGH = "HIGH"       # >= 0.70
    MEDIUM = "MEDIUM"   # 0.40 - 0.70
    LOW = "LOW"         # < 0.40


class ReviveFeatures(BaseModel):
    """Normalized feature vector extracted from observable public event and customer data."""
    event_id: str
    customer_id: str
    amount: float = Field(..., gt=0.0)
    payment_method: str
    payment_method_type: str
    attempt_number: int = Field(default=1, ge=1)
    is_abandoned: bool = False
    checkout_stage: Optional[str] = None
    
    # Failure diagnostics
    failure_category: NormalizedFailureCategory
    error_code: Optional[str] = None
    error_source: Optional[str] = None
    error_step: Optional[str] = None
    error_reason: Optional[str] = None

    # Customer profile & history
    historical_txns: int = 0
    historical_success_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    historical_failures: int = 0
    customer_age_days: int = 0
    customer_avg_amount: float = 0.0
    amount_to_avg_ratio: float = 1.0
    is_new_customer: bool = False
    is_subscription: bool = False
    is_high_value: bool = False

    # Temporal context
    day_of_month: int = 1
    hour_of_day: int = 12
    day_of_week: int = 0
    is_salary_window: bool = False # e.g. 1st-5th of month
    is_month_end_shortage_window: bool = False # e.g. 27th-31st of month


class DiagnosisResult(BaseModel):
    """Structured root-cause diagnosis and classification output."""
    category: NormalizedFailureCategory
    confidence: float = Field(..., ge=0.0, le=1.0, description="Certainty regarding the failure mode")
    risk_signal: RiskSignal
    reason_codes: List[str] = Field(default_factory=list)
    explanation: str


class ActionScore(BaseModel):
    """Expected value and probability score for a single candidate recovery action."""
    action: RecoveryAction
    success_probability: float = Field(..., ge=0.0, le=1.0)
    expected_revenue: float
    action_cost: float
    friction_penalty: float
    expected_value: float
    is_eligible: bool = True


class ReviveRecommendation(BaseModel):
    """Complete intelligence payload produced by the REVIVE scoring engine."""
    event_id: str
    payment_id: Optional[str] = None
    customer_id: str
    timestamp: str
    amount: float
    
    diagnosis: DiagnosisResult
    recoverability_score: float = Field(..., ge=0.0, le=1.0, description="Calibrated recovery likelihood")
    recoverability_tier: RecoverabilityTier
    recommended_action: RecoveryAction
    action_scores: Dict[str, ActionScore]
    
    # Explainability factors
    feature_contributions: Dict[str, float]
    top_positive_factors: List[str]
    top_negative_factors: List[str]


class BatchDiagnosisSummary(BaseModel):
    """Aggregated metrics across a batch of evaluated opportunities."""
    total_opportunities: int
    diagnosis_distribution: Dict[str, int]
    recommended_action_distribution: Dict[str, int]
    recoverability_tier_distribution: Dict[str, int]
    risk_signal_distribution: Dict[str, int]
    average_recoverability_score: float
    average_diagnosis_confidence: float
