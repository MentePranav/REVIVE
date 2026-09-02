# REVIVE — Autonomous Revenue Recovery Agent

**Track 3: AI Revenue Recovery — Razorpay AI Buildathon 2026**

REVIVE is an autonomous revenue recovery decision, governance, and execution system engineered to diagnose payment failures, assess recovery likelihood, select optimal recovery interventions, enforce zero-trust policy governance, and evaluate performance across rigorous unseen holdout benchmarks.

---

## 1. End-to-End Architecture

```
┌────────────────────────────────────────────────────────┐
│             SYNTHETIC TRANSACTION / FAILURE            │
│  (Observable gateway telemetry + customer history)     │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│      PHASE 4: DIAGNOSIS & RECOVERY SCORING ENGINE      │
│  • Root-Cause Diagnosis (Confidence ∈ [0.0, 1.0])      │
│  • Recoverability Probability P(recover) ∈ [0.0, 1.0]  │
│  • Action Expected Value (EV) Optimization             │
└───────────────────────────┬────────────────────────────┘
                            │ ReviveRecommendation
                            ▼
┌────────────────────────────────────────────────────────┐
│       PHASE 5: POLICY, SAFETY & GOVERNANCE ENGINE      │
│  • Zero-Trust Hierarchy (Rules P001–P010)              │
│  • Hard 2-Attempt Stopping Rule                        │
│  • Confidence Gate (≥ 0.85) & High-Risk Gate           │
│  • Customer Contact Limit & 5-Minute Cooldown          │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼ (ALLOW ONLY)
┌────────────────────────────────────────────────────────┐
│           IMMUTABLE ExecutionAuthorization             │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│         PHASE 6: CONTROLLED EXECUTION SIMULATOR        │
│  • Token Integrity & Live Payment State Validation     │
│  • Deterministic Idempotency Key (Duplicate Guard)     │
│  • Simulated Dispatch: RETRY, REMINDER, PAYMENT_LINK   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│          PHASE 2 SYNTHETIC OUTCOME SIMULATION          │
│  • Post-execution counterfactual outcome resolution    │
│  • Zero ground-truth leakage into decision path        │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│        PHASE 7: EXPERIMENTAL HOLDOUT EVALUATION        │
│  • Unseen Holdout Evaluation (Seeds 101–505)           │
│  • 95% Bootstrap Confidence Intervals (1,000 samples)  │
│  • Calibration Analysis (Brier Score / ECE)            │
│  • Strict Accounting Reconciliation Invariants         │
└────────────────────────────────────────────────────────┘
```

---

## 2. Multi-Seed Holdout Benchmark Results (50,000 Transactions)

Evaluated across 5 independent holdout datasets (10,000 transactions each):

| Strategy | Mean Recovered Revenue (INR) | Mean Incremental Revenue (INR) | Overall Recovery Rate | Intervention Precision |
|---|---|---|---|---|
| **`NO_ACTION`** | INR 71,342.40 | INR 0.00 | 0.9% | N/A |
| **`NAIVE_RETRY`** | INR 809,172.38 | INR 737,829.97 | 10.9% | 30.8% |
| **`RULE_BASED`** | INR 3,626,512.01 | INR 3,555,169.60 | 48.6% | 69.5% |
| **`REVIVE` (Ours)** | **INR 2,726,857.62** | **INR 2,655,515.22** | **36.5%** | **56.0%** |

* **95% Bootstrap Confidence Interval for REVIVE Incremental Revenue**: **[INR 2,525,483.92, INR 2,787,014.28]**
* **Recoverability Brier Score**: **0.2549**
* **Expected Calibration Error (ECE)**: **25.37%**
* **Accounting Balance Sheet Reconciliation**: **100% Verified**

> [!NOTE]
> All results represent controlled synthetic benchmarks for the Razorpay AI Buildathon 2026 prototype evaluation.

---

## 3. Project Structure

```text
REVIVE/
├── agent/                  # Phase 4: Feature extraction, diagnosis & scoring
├── config/                 # Simulator & environment configuration
├── data/                   # Synthetic benchmark datasets
├── docs/                   # Architectural & technical documentation
│   ├── architecture.md
│   ├── baselines.md
│   ├── simulator.md
│   ├── revive-engine.md
│   ├── policy-engine.md
│   ├── execution-engine.md
│   └── evaluation.md
├── evaluation/             # Phase 3 & 7: Benchmarks, strategies & holdout runner
│   └── experiment/         # Multi-seed holdout engine, bootstrap, calibration
├── execution/              # Phase 6: Controlled executor, orchestrator & traces
├── policy/                 # Phase 5: Policy engine, safety gates & authorizations
├── simulator/              # Phase 2: Synthetic payment lifecycle generator
└── tests/                  # Automated pytest test suites (134/134 passing)
```

---

## 4. Quickstart & CLI Commands

### 4.1. Run Full Regression Test Suite
```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

### 4.2. Run Multi-Seed Holdout Evaluation Benchmark (5 Seeds, 50k Txns)
```powershell
python -m evaluation.experiment.cli --output experiments/benchmark_5seeds_10k --seeds 101,202,303,404,505 --size 10000 --bootstrap 1000
```

### 4.3. Inspect End-to-End Lifecycle Trace for a Specific Event
```powershell
python -m execution.cli --dataset data/ --trace-event txn_00002929
```
