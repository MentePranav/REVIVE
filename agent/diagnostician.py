"""
Diagnostics Engine for REVIVE.
Classifies root causes, assesses diagnostic confidence, and produces risk signals.
"""

from typing import List, Tuple
from agent.models import DiagnosisResult, NormalizedFailureCategory, ReviveFeatures, RiskSignal


class DiagnosticsEngine:
    """Evaluates observable contextual signals to produce root-cause diagnoses and confidence ratings."""

    @classmethod
    def diagnose(cls, features: ReviveFeatures) -> DiagnosisResult:
        cat = features.failure_category
        reason_codes: List[str] = []
        
        # 1. Evaluate Risk Signal
        risk_signal = cls._assess_risk_signal(features, reason_codes)

        # 2. Compute Category-Specific Diagnosis & Confidence
        if cat == NormalizedFailureCategory.TRANSIENT:
            confidence, explanation = cls._diagnose_transient(features, reason_codes)
        elif cat == NormalizedFailureCategory.INSUFFICIENT_FUNDS:
            confidence, explanation = cls._diagnose_insufficient_funds(features, reason_codes)
        elif cat == NormalizedFailureCategory.AUTHENTICATION:
            confidence, explanation = cls._diagnose_authentication(features, reason_codes)
        elif cat == NormalizedFailureCategory.BANK_DECLINE:
            confidence, explanation = cls._diagnose_bank_decline(features, reason_codes)
        elif cat == NormalizedFailureCategory.PAYMENT_METHOD:
            confidence, explanation = cls._diagnose_payment_method(features, reason_codes)
        elif cat == NormalizedFailureCategory.ABANDONMENT:
            confidence, explanation = cls._diagnose_abandonment(features, reason_codes)
        elif cat == NormalizedFailureCategory.HARD_FAILURE:
            confidence, explanation = cls._diagnose_hard_failure(features, reason_codes)
        elif cat == NormalizedFailureCategory.HIGH_RISK:
            confidence, explanation = cls._diagnose_high_risk(features, reason_codes)
        else:
            confidence = 0.35
            explanation = "Unclassified or missing failure diagnostics; diagnostic confidence is low."
            reason_codes.append("UNCLASSIFIED_FAILURE_TELEMETRY")

        # 3. Penalize confidence for new customers or extreme amount anomalies (Conflicting signals)
        if features.is_new_customer and cat not in (NormalizedFailureCategory.ABANDONMENT, NormalizedFailureCategory.HARD_FAILURE):
            confidence = max(0.30, confidence - 0.20)
            reason_codes.append("NEW_CUSTOMER_LIMITED_HISTORY_PENALTY")

        if features.amount_to_avg_ratio >= 5.0 and features.historical_txns >= 5:
            confidence = max(0.40, confidence - 0.15)
            reason_codes.append("AMOUNT_ANOMALY_AMBIGUITY")

        return DiagnosisResult(
            category=cat,
            confidence=round(min(1.0, max(0.1, confidence)), 4),
            risk_signal=risk_signal,
            reason_codes=reason_codes,
            explanation=explanation
        )

    @classmethod
    def _assess_risk_signal(cls, f: ReviveFeatures, reason_codes: List[str]) -> RiskSignal:
        if f.failure_category == NormalizedFailureCategory.HIGH_RISK:
            reason_codes.append("GATEWAY_RISK_FLAG_PRESENT")
            return RiskSignal.HIGH

        if f.amount >= 50000.0 and f.amount_to_avg_ratio >= 8.0:
            reason_codes.append("EXTREME_VELOCITY_AMOUNT_SURGE")
            return RiskSignal.HIGH

        if f.is_new_customer and f.amount >= 25000.0:
            reason_codes.append("HIGH_VALUE_NEW_ACCOUNT_CAUTION")
            return RiskSignal.MEDIUM

        if f.historical_failures >= 5 and f.historical_success_rate < 0.40:
            reason_codes.append("CHRONIC_DELINQUENCY_SIGNAL")
            return RiskSignal.MEDIUM

        return RiskSignal.LOW

    @classmethod
    def _diagnose_transient(cls, f: ReviveFeatures, reason_codes: List[str]) -> Tuple[float, str]:
        reason_codes.append("GATEWAY_PROCESSOR_TIMEOUT")
        if f.historical_success_rate >= 0.90 and f.historical_txns >= 5:
            reason_codes.append("ISOLATED_INCIDENT_ON_LOYAL_CUSTOMER")
            return 0.94, "Transient infrastructure/gateway timeout on established reliable customer."
        elif f.historical_success_rate >= 0.70:
            return 0.82, "Transient timeout during authorization; moderate customer reliability."
        else:
            reason_codes.append("TIMEOUT_WITH_MIXED_HISTORY")
            return 0.68, "Gateway timeout observed, but customer history shows frequent prior friction."

    @classmethod
    def _diagnose_insufficient_funds(cls, f: ReviveFeatures, reason_codes: List[str]) -> Tuple[float, str]:
        reason_codes.append("INSUFFICIENT_BALANCE_DECLINE")
        if f.is_month_end_shortage_window:
            reason_codes.append("MONTH_END_LIQUIDITY_PATTERN")
            return 0.91, "Insufficient funds decline aligned with month-end liquidity cycle."
        elif f.is_salary_window:
            reason_codes.append("EARLY_MONTH_ANOMALY")
            return 0.84, "Insufficient balance observed during early-month salary window."
        else:
            return 0.88, "Standard customer account insufficient balance authorization decline."

    @classmethod
    def _diagnose_authentication(cls, f: ReviveFeatures, reason_codes: List[str]) -> Tuple[float, str]:
        reason_codes.append("AUTHENTICATION_3DS_OTP_DROP")
        if f.historical_txns >= 3:
            return 0.92, "Customer dropped or mis-entered OTP during two-factor authentication."
        else:
            return 0.78, "Authentication failure during onboarding/first payment."

    @classmethod
    def _diagnose_bank_decline(cls, f: ReviveFeatures, reason_codes: List[str]) -> Tuple[float, str]:
        reason_codes.append("ISSUING_BANK_REJECTION")
        if f.is_high_value:
            reason_codes.append("HIGH_VALUE_BANK_AUTH_LIMIT")
            return 0.89, "Bank decline likely attributable to single-transaction authorization ceiling."
        else:
            return 0.79, "Generic bank decline without explicit sub-code from issuer."

    @classmethod
    def _diagnose_payment_method(cls, f: ReviveFeatures, reason_codes: List[str]) -> Tuple[float, str]:
        reason_codes.append("PAYMENT_INSTRUMENT_INVALID_OR_EXPIRED")
        if f.is_subscription:
            reason_codes.append("RECURRING_MANDATE_EXPIRY")
            return 0.93, "Mandate payment instrument expired or revoked on recurring subscription."
        else:
            return 0.86, "Payment card expired or UPI VPA inactive."

    @classmethod
    def _diagnose_abandonment(cls, f: ReviveFeatures, reason_codes: List[str]) -> Tuple[float, str]:
        reason_codes.append(f"CHECKOUT_DROP_STAGE_{f.checkout_stage or 'UNKNOWN'}")
        if f.checkout_stage in ("OTP_STAGE", "PAYMENT_SUBMISSION"):
            return 0.90, "High-intent checkout abandoned at final payment verification stage."
        else:
            return 0.85, "Early-funnel checkout session abandonment."

    @classmethod
    def _diagnose_hard_failure(cls, f: ReviveFeatures, reason_codes: List[str]) -> Tuple[float, str]:
        reason_codes.append("TERMINAL_ACCOUNT_BLOCK")
        return 0.96, "Permanent account or instrument block reported by issuing bank."

    @classmethod
    def _diagnose_high_risk(cls, f: ReviveFeatures, reason_codes: List[str]) -> Tuple[float, str]:
        reason_codes.append("FRAUD_VELOCITY_RISK_BLOCK")
        return 0.92, "Gateway automated risk filter triggered by anomalous velocity or fraud pattern."
