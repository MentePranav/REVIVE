"""
Failure Analysis and Vulnerability Diagnostic Engine for REVIVE Phase 7.
Identifies false positive interventions, unnecessary retries, missed high-value opportunities, and weak operational segments.
"""

from typing import Dict, List, Union
from agent.models import NormalizedFailureCategory, RiskSignal
from evaluation.experiment.models import FailureAnalysisReport, SegmentMetrics
from execution.models import ExecutionLifecycleTrace, ExecutionStatus, SimulatedRecoveryOutcome
from policy.models import PolicyDecisionType
from simulator.enums import RecoveryAction
from simulator.ground_truth_schema import GroundTruthRecord
from simulator.public_schema import AbandonedCheckout, Transaction


class FailureAnalyzer:
    """Diagnoses failure modes, friction points, and operational vulnerabilities."""

    @staticmethod
    def analyze(
        traces: List[ExecutionLifecycleTrace],
        events_by_id: Dict[str, Union[Transaction, AbandonedCheckout]],
        ground_truth_map: Dict[str, GroundTruthRecord],
        segment_metrics: List[SegmentMetrics]
    ) -> FailureAnalysisReport:
        fp_interventions = 0
        unnecessary_retries = 0
        high_risk_leaks = 0
        low_conf_escalations = 0
        unrecovered_hv_count = 0
        unrecovered_hv_rev = 0.0

        for t in traces:
            event = events_by_id.get(t.event_id)
            if not event:
                continue

            amount = float(event.amount)
            is_attempted = (t.execution_result.execution_status == ExecutionStatus.EXECUTED)
            is_recovered = (t.execution_result.recovery_outcome in (SimulatedRecoveryOutcome.RECOVERED, SimulatedRecoveryOutcome.NATURAL_RECOVERY))

            # 1. False Positive Interventions (intervened on unrecoverable opportunity)
            if is_attempted and not is_recovered:
                fp_interventions += 1

            # 2. Unnecessary Retries (retried an unrecoverable transaction)
            if is_attempted and t.execution_result.authorized_action == RecoveryAction.RETRY and not is_recovered:
                unnecessary_retries += 1

            # 3. High-Risk Automated Leaks (asserting zero tolerance)
            is_high_risk = (
                t.recommendation.diagnosis.risk_signal == RiskSignal.HIGH or
                t.recommendation.diagnosis.category == NormalizedFailureCategory.HIGH_RISK
            )
            if is_attempted and is_high_risk:
                high_risk_leaks += 1

            # 4. Low-Confidence Escalations
            if t.policy_decision.decision == PolicyDecisionType.HUMAN_REVIEW and "confidence" in t.policy_decision.reason.lower():
                low_conf_escalations += 1

            # 5. Missed High-Value Opportunities (>= INR 10,000 not recovered)
            if amount >= 10000.0 and not is_recovered:
                unrecovered_hv_count += 1
                unrecovered_hv_rev += amount

        # 6. Weak Segments (precision or recovery rate < 25%)
        weak_segs: List[str] = []
        for s in segment_metrics:
            if s.total_opportunities >= 20 and s.intervention_precision < 0.25 and s.interventions_attempted > 0:
                weak_segs.append(f"{s.segment_type}:{s.segment_value} (Precision: {s.intervention_precision * 100:.1f}%)")

        return FailureAnalysisReport(
            false_positive_interventions=fp_interventions,
            unnecessary_retries=unnecessary_retries,
            high_risk_automated_leaks=high_risk_leaks,
            low_confidence_escalations=low_conf_escalations,
            unrecovered_high_value_count=unrecovered_hv_count,
            unrecovered_high_value_revenue=round(unrecovered_hv_rev, 2),
            weak_segments=weak_segs
        )
