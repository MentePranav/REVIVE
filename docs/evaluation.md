# REVIVE — Experimental Evaluation, Holdout Benchmarking & Revenue Recovery Proof

## 1. Executive Summary & Purpose

The **REVIVE Experimental Evaluation Framework** provides a scientifically grounded benchmarking system to prove whether REVIVE recovers incremental revenue over baseline strategies while strictly enforcing safety, customer fatigue limits, and zero-trust policy governance.

> [!IMPORTANT]
> **Simulation Disclaimer**: All benchmarks operate exclusively on synthetic datasets generated for the Razorpay AI Buildathon 2026. All financial amounts and recovery rates represent controlled simulation outcomes rather than real Razorpay production figures.

```
┌────────────────────────────────────────────────────────┐
│             SYNTHETIC DATASET GENERATOR                │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│               DATASET SPLITTER & SEED ISOLATION        │
│  • Development Set (Seed 42, 2k txns) → Thresholds     │
│  • Evaluation Sets (Seeds 101-505, 10k txns each)      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│             FAIR BENCHMARK EXECUTION MATRIX            │
│  • NO_ACTION Strategy                                  │
│  • NAIVE_RETRY Strategy                                │
│  • RULE_BASED Strategy                                 │
│  • REVIVE (Phase 4 Scoring + Phase 5 Policy + Phase 6) │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│          STATISTICAL AGGREGATION & CALIBRATION         │
│  • Mean, Std, Median, Min, Max over multiple seeds     │
│  • 95% Non-Parametric Bootstrap Confidence Intervals   │
│  • Brier Score & 10-Bin Expected Calibration Error     │
│  • Segment Breakdown & Failure Diagnostic Analysis     │
│  • Strict Accounting Reconciliation Invariants         │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│           BENCHMARK_REPORT.md & CLAIM GUARDRAILS       │
└────────────────────────────────────────────────────────┘
```

---

## 2. Development vs. Holdout Evaluation Design

To eliminate selection bias and prevent overfitting:
* **Development Dataset**: Seed `42` (2,000 transactions). Used exclusively for exploratory analysis, calibration inspection, and parameter freezing (e.g. recoverability threshold $\ge 0.70$, confidence threshold $\ge 0.85$).
* **Evaluation Holdout Sets**: Independent, unseen seeds `101, 202, 303, 404, 505` (10,000 transactions each). Evaluated only after all parameters have been frozen.

---

## 3. Strict Zero-Leakage Guarantee

* **Decision-Time Isolation**: Strategies receive only observable public models (`Transaction`, `AbandonedCheckout`, `Customer`).
* **Post-Execution Evaluation**: Ground truth (`GroundTruthRecord`) and counterfactual resolution matrices are passed exclusively to the outcome evaluation layer **after** the action has been selected, authorized, and dispatched.

---

## 4. Primary Business Metric: Incremental Recovered Revenue

The primary benchmark metric is **Incremental Recovered Revenue** ($\Delta R$):

$$\Delta R = R_{\text{REVIVE}} - R_{\text{NO\_ACTION}}$$

Where:
* $R_{\text{REVIVE}}$: Total revenue captured following REVIVE intervention.
* $R_{\text{NO\_ACTION}}$: Revenue recovered naturally by customers without any intervention.

---

## 5. Multi-Seed Holdout Benchmark Results (50,000 Transactions Total)

Evaluated across 5 independent holdout datasets of 10,000 transactions each (Seeds 101, 202, 303, 404, 505):

| Strategy | Mean Recovered Revenue (INR) | Mean Incremental Revenue (INR) | Overall Recovery Rate | Intervention Precision |
|---|---|---|---|---|
| **`NO_ACTION`** | INR 71,342.40 | INR 0.00 | 0.9% | N/A |
| **`NAIVE_RETRY`** | INR 809,172.38 | INR 737,829.97 | 10.9% | 30.8% |
| **`RULE_BASED`** | INR 3,626,512.01 | INR 3,555,169.60 | 48.6% | 69.5% |
| **`REVIVE` (Ours)** | **INR 2,726,857.62** | **INR 2,655,515.22** | **36.5%** | **56.0%** |

* **REVIVE 95% Bootstrap Confidence Interval**: **[INR 2,525,483.92, INR 2,787,014.28]**

> [!NOTE]
> While unconstrained rule-based systems aggressively retry without policy constraints, REVIVE intentionally routes 30.4% of opportunities to human review and enforces strict 2-attempt stopping caps, zero-risk leak tolerance ($P005$), and customer contact limits ($P007$).

---

## 6. Model Calibration & Reliability

* **Brier Score**: **0.2549**
* **Expected Calibration Error (ECE)**: **25.37%**
* **Reliability**: Tested across 10 uniform probability bins $[0.0, 0.1), \dots, [0.9, 1.0]$.

---

## 7. Accounting Invariants Verification

For every evaluation seed, the accounting engine verifies:
1. $\text{Revenue at Risk} = \text{Recovered Revenue} + \text{Unrecovered Revenue}$ (Zero reconciliation discrepancy).
2. $\Delta R = R_{\text{REVIVE}} - R_{\text{NO\_ACTION}}$ exactly.
3. $\text{Recovered Revenue} \le \text{Revenue at Risk}$.
4. Zero duplicate transaction recovery contributions.

---

## 8. Reproducibility Command

To run the complete holdout evaluation benchmark and generate all artifacts locally:

```powershell
python -m evaluation.experiment.cli --output experiments/benchmark_5seeds_10k --seeds 101,202,303,404,505 --size 10000 --bootstrap 1000
```
