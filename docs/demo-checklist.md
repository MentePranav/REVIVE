# REVIVE — Buildathon Presentation & Evaluator Demo Checklist

This document provides the exact step-by-step procedure for demonstrating REVIVE to evaluators and hackathon judges.

---

## 1. Pre-Flight Checklist (1 Minute Before Demo)

1. **Verify Local Environment**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/ -q
   # Expected: 177 passed in ~9.5s
   ```
2. **Launch Application**:
   Double click `start_revive.bat` or run:
   ```powershell
   .\.venv\Scripts\python.exe -m server.cli --port 8000
   ```
3. **Open Browser**:
   Navigate to [http://localhost:8000](http://localhost:8000).

---

## 2. Recommended 3-Minute Live Demo Flow

### Step 1: Overview & Value Proposition (0:00 - 0:45)
- **Point to Top KPIs**:
  - **Revenue At Risk**: Show total synthetic volume lost to payment friction.
  - **Incremental Revenue (ΔR)**: Highlight INR 2.65M+ recovered revenue above passive baseline.
  - **Intervention Precision**: Show 56.04% precision vs. 30.84% blind naive retry.
  - **Safety Blocks**: Point out that dangerous/unauthorized interventions are actively stopped.
- **Narrative**: *"Merchants lose substantial revenue when transactions fail. Blind retries spam customers and trigger bank penalties. REVIVE uses contextual diagnosis and zero-trust governance to intervene only when safe and profitable."*

### Step 2: The 3 Core Scenarios (0:45 - 2:00)
Switch to the **Recovery Cases** tab:

1. **Scenario 1: Intelligent Transient Recovery (UPI Timeout)**
   - Search for a transient failure case.
   - Click **Inspect**.
   - Show:
     - **Phase 4 Intelligence**: High confidence (95%), Recoverability Score (~85%), EV analysis shows `RETRY` yields the highest net expected value.
     - **Phase 5 Safety Gate**: All 7 safety rules passed (`P010_ACTION_APPROVED`), `ExecutionAuthorization` token issued.
     - **Controlled Execution**: Click **Execute Simulated Recovery**. Notice instant status update to `RECOVERED` and external reference recorded.

2. **Scenario 2: Zero-Tolerance High-Risk Block (Fraud & Dispute Prevention)**
   - Filter cases by status: `Human Review` or search for `HIGH_RISK`.
   - Click **Inspect**.
   - Show:
     - **Risk Signal**: `HIGH` risk flag.
     - **Policy Rule**: Triggered `P005_HIGH_RISK_GATE`.
     - **Safety Invariant**: Automated execution button is completely disabled. System routes to risk review instead of risking chargeback penalties.

3. **Scenario 3: Hard Attempt Cap & Fatigue Guard (P003 / P007)**
   - Show how cases with prior attempts or contact exhaustion are blocked from receiving duplicate spam reminders.

### Step 3: Comparative Benchmark & Tradeoff Walkthrough (2:00 - 2:45)
- Switch to the **Benchmark** tab.
- Explain the 4-way strategy comparison across 50,000 transactions (Seeds 101–505):
  - `NO_ACTION`: 0.94% passive recovery.
  - `NAIVE_RETRY`: 10.86% recovery but creates 69.16% customer friction on permanent declines.
  - `RULE_BASED`: 48.58% recovery; unconstrained by fraud gates or attempt caps.
  - `REVIVE`: 36.53% recovery, delivering **INR 2,655,515.22 in incremental revenue** while **reducing interventions by 22.4%**, escalating 624 low-confidence cases to human review, and permitting zero automated high-risk actions.

### Step 4: Live Reset & Wrap-up (2:45 - 3:00)
- Click **Reset Demo** in the top navigation bar to demonstrate deterministic state restoration.
- Conclude: *"REVIVE delivers actionable revenue recovery with institutional-grade risk governance and complete audit transparency."*

---

## 3. Evaluator FAQ Quick Reference

- **Q: Why does the unconstrained RULE_BASED baseline have higher gross revenue?**
  *A: In this simulator, the rule-based strategy aggressively acts on every failure without stopping rules or risk boundaries. REVIVE was intentionally designed for governed recovery: trading some gross revenue to reduce interventions by 22.4%, cap automated attempts at 2, respect customer fatigue, and allow zero automated high-risk fraud actions.*
- **Q: Are real payment networks or cards being charged?**
  *A: No. REVIVE operates in a statistically controlled, deterministic local simulation environment to protect payment credentials while enabling rigorous scientific benchmarking.*
- **Q: How is ground truth isolated from the AI model?**
  *A: The feature extractor only receives observable public transaction schemas. Ground truth counterfactual matrices are strictly isolated and queried only inside the post-authorization execution sandbox.*
- **Q: Can the web UI execute arbitrary actions?**
  *A: No. The backend validates the cryptographic `ExecutionAuthorization` token issued by Phase 5 and verifies live payment state before dispatching any simulated action.*
