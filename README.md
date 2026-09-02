# REVIVE — Autonomous Revenue Recovery Agent

**Track 3: AI Revenue Recovery — Razorpay AI Buildathon 2026**

REVIVE is an autonomous revenue recovery decision and execution system engineered to diagnose payment failures, assess recovery likelihood, select optimal recovery interventions, enforce zero-trust policy governance, and execute controlled synthetic recovery workflows.

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
│            IMMUTABLE AUDIT TRAIL & TRACE LOG           │
└────────────────────────────────────────────────────────┘
```

---

## 2. Why the Safety Boundary Exists

In automated revenue recovery, optimization models cannot be trusted with unconstrained execution authority. REVIVE enforces the core security invariant:

> **Optimization may recommend. Policy may authorize. Execution may act.**

1. **Zero-Trust Validation**: An action is never executed simply because the scoring engine predicted high revenue.
2. **Hard Attempt Caps**: Hard limit of maximum 2 automated recovery attempts per payment to prevent infinite retry loops.
3. **Double-Recovery Prevention**: Payments that became resolved/captured are structurally blocked from execution.
4. **Customer Fatigue Protection**: Contact caps and 5-minute cooldowns prevent messaging spam.
5. **Fail-Closed Execution**: If any authorization or state invariant fails, the system safely halts without triggering unverified actions.

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
│   └── execution-engine.md
├── evaluation/             # Phase 3: Benchmarks & baseline strategies
├── execution/              # Phase 6: Controlled executor, orchestrator & CLI
├── policy/                 # Phase 5: Policy engine, safety gates & authorizations
├── simulator/              # Phase 2: Synthetic payment lifecycle generator
└── tests/                  # Automated pytest test suites (103/103 passing)
```

---

## 4. Quickstart & CLI Commands

### 4.1. Run Full Regression Test Suite
```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

### 4.2. Run Comparative Baseline Benchmark
```powershell
python -m evaluation.compare --dataset data/ --output data/evaluations/
```

### 4.3. Run End-to-End Controlled Execution Simulation
```powershell
python -m execution.cli --dataset data/ --output data/execution_analysis/
```

### 4.4. Inspect End-to-End Lifecycle Trace for a Specific Event
```powershell
python -m execution.cli --dataset data/ --trace-event txn_00002929
```
