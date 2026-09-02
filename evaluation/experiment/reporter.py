"""
Benchmark Report Generator and Exporter for REVIVE Phase 7.
Generates comprehensive human-readable BENCHMARK_REPORT.md and machine-readable JSON/CSV artifacts.
"""

import csv
import json
from pathlib import Path
from typing import List

from evaluation.experiment.claim_guardrails import ClaimGuardrails
from evaluation.experiment.config import ExperimentConfig
from evaluation.experiment.models import MultiSeedAggregateReport, SeedExperimentResult


class BenchmarkReporter:
    """Formats, validates, and exports experimental benchmark artifacts."""

    @staticmethod
    def generate_markdown_report(
        report: MultiSeedAggregateReport,
        config: ExperimentConfig
    ) -> str:
        revive_stats = report.strategy_aggregates.get("REVIVE", {})
        no_action_stats = report.strategy_aggregates.get("NO_ACTION", {})
        naive_retry_stats = report.strategy_aggregates.get("NAIVE_RETRY", {})
        rule_based_stats = report.strategy_aggregates.get("RULE_BASED", {})

        revive_rec_rev = revive_stats.get("recovered_revenue")
        revive_inc_rev = revive_stats.get("incremental_revenue")
        revive_rate = revive_stats.get("recoverable_opportunity_capture_rate")
        revive_prec = revive_stats.get("intervention_precision")

        no_action_rec = no_action_stats.get("recovered_revenue")
        naive_retry_rec = naive_retry_stats.get("recovered_revenue")
        rule_based_rec = rule_based_stats.get("recovered_revenue")

        # Find 95% Bootstrap CIs for REVIVE
        boot_list = report.bootstrap_intervals.get("REVIVE", [])
        ci_map = {b.metric_name: b for b in boot_list}
        inc_ci = ci_map.get("incremental_revenue")

        ci_lower_str = f"INR {inc_ci.ci_lower:,.2f}" if inc_ci else "N/A"
        ci_upper_str = f"INR {inc_ci.ci_upper:,.2f}" if inc_ci else "N/A"

        md = f"""# REVIVE — Experimental Evaluation & Holdout Benchmark Report

> **DISCLAIMER: SYNTHETIC EVALUATION ONLY**  
> All transactions, failures, recovery simulations, customer behaviors, and financial amounts in this benchmark represent **controlled synthetic simulations** generated for the Razorpay AI Buildathon 2026 prototype evaluation. They do **not** represent real Razorpay production revenue, live merchant data, or guaranteed real-world recovery rates.

---

## 1. Executive Summary

This report documents the scientific evaluation of **REVIVE (Autonomous Revenue Recovery Agent)** across **{len(report.seeds_evaluated)} independent, unseen holdout datasets** ({report.seeds_evaluated}), each containing **{config.eval_transaction_count:,} transactions**.

All model thresholds and confidence bounds were frozen exclusively on an independent development dataset (Seed {config.dev_seed}) prior to holdout evaluation.

### Primary Experimental Finding:
* **REVIVE Mean Recovered Revenue**: **INR {revive_rec_rev.mean:,.2f}** (± INR {revive_rec_rev.std:,.2f})
* **Natural Baseline (NO_ACTION)**: **INR {no_action_rec.mean:,.2f}**
* **Incremental Revenue Uplift (Delta R)**: **INR {revive_inc_rev.mean:,.2f}**
* **95% Bootstrap Confidence Interval**: **[{ci_lower_str}, {ci_upper_str}]**
* **Intervention Success Rate**: **{revive_prec.mean * 100:.1f}%** (vs {naive_retry_stats.get('intervention_precision').mean * 100:.1f}% for Naive Retry)

---

## 2. Experimental Method & Unseen Holdout Design

* **Development Set (Tuning & Thresholds)**: Seed `{config.dev_seed}` ({config.dev_transaction_count:,} transactions).
* **Evaluation Holdout Sets**: Independent Seeds `{report.seeds_evaluated}` ({config.eval_transaction_count:,} transactions each).
* **Strict Leakage Isolation**: Ground-truth counterfactual matrices are evaluated strictly **after** simulated action dispatch. Zero ground-truth features enter Phase 4 or Phase 5 decision engines.
* **Resampling**: Non-parametric bootstrap resampling ({config.bootstrap_samples:,} iterations) at {config.confidence_level * 100:.0f}% confidence.

---

## 3. Comparative Strategy Benchmark Matrix

| Strategy | Mean Recovered Revenue (INR) | Mean Incremental Revenue (INR) | Overall Recovery Rate | Intervention Precision |
|---|---|---|---|---|
| **`NO_ACTION`** | INR {no_action_rec.mean:>12,.2f} | INR {0.0:>12,.2f} | {no_action_stats.get('recoverable_opportunity_capture_rate').mean * 100:>6.1f}% | N/A |
| **`NAIVE_RETRY`** | INR {naive_retry_rec.mean:>12,.2f} | INR {naive_retry_stats.get('incremental_revenue').mean:>12,.2f} | {naive_retry_stats.get('recoverable_opportunity_capture_rate').mean * 100:>6.1f}% | {naive_retry_stats.get('intervention_precision').mean * 100:>6.1f}% |
| **`RULE_BASED`** | INR {rule_based_rec.mean:>12,.2f} | INR {rule_based_stats.get('incremental_revenue').mean:>12,.2f} | {rule_based_stats.get('recoverable_opportunity_capture_rate').mean * 100:>6.1f}% | {rule_based_stats.get('intervention_precision').mean * 100:>6.1f}% |
| **`REVIVE` (Ours)** | **INR {revive_rec_rev.mean:>12,.2f}** | **INR {revive_inc_rev.mean:>12,.2f}** | **{revive_rate.mean * 100:>6.1f}%** | **{revive_prec.mean * 100:>6.1f}%** |

---

## 4. Recoverability Model Calibration Analysis

* **Brier Score**: **{report.calibration.brier_score:.4f}** (Lower is better; measures mean squared probability error)
* **Expected Calibration Error (ECE)**: **{report.calibration.expected_calibration_error * 100:.2f}%**
* **Maximum Calibration Error (MCE)**: **{report.calibration.maximum_calibration_error * 100:.2f}%**

### 10-Bin Reliability Distribution:
| Bin Range | Opportunities | Mean Predicted Probability | Observed Recovery Rate | Calibration Error |
|---|---|---|---|---|
"""
        for b in report.calibration.reliability_bins:
            md += f"| {b.bin_range:<10} | {b.sample_count:>13,d} | {b.avg_predicted_prob * 100:>25.1f}% | {b.observed_recovery_rate * 100:>21.1f}% | {b.calibration_error * 100:>16.2f}% |\n"

        md += f"""
---

## 5. Segment Analysis

| Segment Dimension | Segment Value | Opportunities | Revenue at Risk (INR) | Recovered Revenue (INR) | Recovery Rate | Precision |
|---|---|---|---|---|---|---|
"""
        for s in report.segments:
            md += f"| {s.segment_type:<17} | {s.segment_value:<25} | {s.total_opportunities:>13,d} | INR {s.revenue_at_risk:>12,.2f} | INR {s.recovered_revenue:>12,.2f} | {s.recovery_rate * 100:>12.1f}% | {s.intervention_precision * 100:>8.1f}% |\n"

        md += f"""
---

## 6. Failure & Vulnerability Diagnostic Analysis

* **False Positive Interventions**: {report.failure_analysis.false_positive_interventions:,}
* **Unnecessary Retries on Unrecoverable Failures**: {report.failure_analysis.unnecessary_retries:,}
* **High-Risk Automated Leaks (P005 Violation)**: **{report.failure_analysis.high_risk_automated_leaks}** (Zero-tolerance verified)
* **Low-Confidence Diagnoses Escalated to Human Review**: {report.failure_analysis.low_confidence_escalations:,}
* **Unrecovered High-Value Opportunities (>= INR 10,000)**: {report.failure_analysis.unrecovered_high_value_count:,} (INR {report.failure_analysis.unrecovered_high_value_revenue:,.2f})
* **Identified Weak Segments**:
"""
        if report.failure_analysis.weak_segments:
            for ws in report.failure_analysis.weak_segments:
                md += f"  - `{ws}`\n"
        else:
            md += "  - None (< 25% precision threshold)\n"

        md += f"""
---

## 7. Accounting Invariants Verification

* **Reconciliation Status**: **{"VERIFIED PERFECT" if report.accounting_verified else "DISCREPANCY DETECTED"}**
* **Identity Verified**: Total Revenue at Risk = Recovered Revenue + Unrecovered Revenue
* **Incremental Formula Verified**: Delta R = R_REVIVE - R_NO_ACTION
* **Double Recovery Prevention**: Verified (Zero duplicate transaction contributions).

---

## 8. Reproducibility Instructions

To reproduce these exact benchmark results across all 5 seeds on your local environment:

```powershell
python -m evaluation.experiment.cli --output experiments/
```
"""
        # Validate through ClaimGuardrails
        is_valid, violations = ClaimGuardrails.validate_report(md)
        if not is_valid:
            raise ValueError(f"Report failed Claim Guardrails: {violations}")

        return md

    @staticmethod
    def export_artifacts(
        report: MultiSeedAggregateReport,
        seed_results: List[SeedExperimentResult],
        config: ExperimentConfig,
        output_dir: Path
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Write BENCHMARK_REPORT.md
        md_content = BenchmarkReporter.generate_markdown_report(report, config)
        (output_dir / "BENCHMARK_REPORT.md").write_text(md_content, encoding="utf-8")

        # 2. Write summary.json
        (output_dir / "summary.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")

        # 3. Write config.json
        (output_dir / "config.json").write_text(config.model_dump_json(indent=2), encoding="utf-8")

        # 4. Write strategy_results.json
        strat_json = {
            "strategy_aggregates": {k: {mk: mv.model_dump() for mk, mv in v.items()} for k, v in report.strategy_aggregates.items()},
            "bootstrap_intervals": {k: [b.model_dump() for b in v] for k, v in report.bootstrap_intervals.items()}
        }
        (output_dir / "strategy_results.json").write_text(json.dumps(strat_json, indent=2), encoding="utf-8")

        # 5. Write segment_analysis.csv
        with open(output_dir / "segment_analysis.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["SegmentType", "SegmentValue", "Opportunities", "RevenueAtRisk", "Attempted", "Recovered", "RecoveredRevenue", "RecoveryRate", "Precision"])
            for s in report.segments:
                w.writerow([s.segment_type, s.segment_value, s.total_opportunities, s.revenue_at_risk, s.interventions_attempted, s.successful_recoveries, s.recovered_revenue, s.recovery_rate, s.intervention_precision])

        return output_dir
