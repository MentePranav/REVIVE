# REVIVE — Evaluator Demo Runbook & Step-by-Step Guide

**Target Evaluation Time:** ~5 Minutes  
**Track:** Track 3: AI Revenue Recovery — Razorpay AI Buildathon 2026  
**Environment:** 100% Local & Self-Contained (Zero External Network Dependencies)

---

## 1. Prerequisites & Startup

### Option A: Windows One-Click Launcher
Double-click `start_revive.bat` in the repository root directory.

### Option B: Terminal Command (All Platforms)
```bash
python -m server.cli --port 8000 --host 127.0.0.1
```

### Verification & Health Check
Open your browser to: **`http://localhost:8000/api/health`**
- Expected JSON response: `"status": "healthy"`, `"reproducibility_fingerprint": "35b2e65d2efaa521"`, `"environment_valid": true`.

Open the Web UI: **`http://localhost:8000`**

---

## 2. Five-Minute Evaluator Demo Script (0:00 – 5:00)

### 0:00–0:30 | Problem & Solution Context
- **Problem**: Digital commerce loses billions to failed transactions and abandoned carts. Blind retries cause issuer throttling and fee waste; uncoordinated spam damages customer trust; uncontrolled retrying of high-risk accounts creates fraud chargebacks.
- **REVIVE**: A governed autonomous revenue recovery decision-and-execution system. It diagnoses root causes, estimates recoverability, enforces institutional safety boundaries, and executes only validated actions authorized after policy gates pass.

---

### 0:30–1:15 | Architecture & Zero-Trust Boundary
- Point out the core invariant: **Recommendation ≠ Authorization**.
$$\text{Untrusted Input} \longrightarrow \text{Contextual Intelligence} \longrightarrow \text{Policy Gate (P001-P010)} \longrightarrow \text{Execution Authorization} \longrightarrow \text{Controlled Executor} \longrightarrow \text{Audit Log}$$
- The execution engine will refuse to act without an explicit, validated `ExecutionAuthorization` token.

---

### 1:15–2:45 | Live Control Center Walkthrough

#### Step 1: Default Golden Session Initialization
1. Click **Reset Demo** in the top navigation bar.
2. **Observe**: The application reloads into the deterministic default Golden State (**Seed 42, 100 Transactions**).
3. **Check Top KPIs**:
   - **Revenue At Risk**: Displays total synthetic failed volume.
   - **Incremental Revenue ($\Delta R$)**: Shows net revenue recovered above passive baseline.
   - **Intervention Precision**: Shows percentage of automated interventions that recovered revenue.
   - **Safety Blocks**: Displays interventions prevented by the Zero-Trust Policy Engine.

#### Step 2: Intelligent Successful Recovery (Transient Gateway Timeout)
1. In the Recovery Cases Table, look for a case with **Policy Decision: `ALLOW`** (e.g. `txn_00000066`).
2. Click **Inspect** on the case:
   - **Intelligence**: Reports failure category (`TRANSIENT`), high confidence ($\ge 90\%$), and high recoverability score.
   - **Safety Gate**: All 10 rules show green checkmarks, and primary rule is `P010_ACTION_APPROVED`.
   - **Authorization Token**: A validated `ExecutionAuthorization` (`auth_...`) is issued only after all policy gates pass.
3. Click **Execute Action**.
4. **Observe**: Execution status transitions to `EXECUTED`, outcome changes to `RECOVERED`, and a synthetic reference (`sim_pl_...`) is logged in the audit trail.

---

### 2:45–3:35 | Safety & Governance Demonstration

#### Step 3: Low Diagnostic Confidence Escalation ($P004$ Human Review Gate)
1. Filter the status dropdown by **`HUMAN_REVIEW_REQUIRED`**.
2. Click **Inspect** on a case with **Primary Rule: `P004_LOW_DIAGNOSIS_CONFIDENCE`**:
   - **Observe**: Model confidence is below the $85\%$ threshold.
   - **Safety Invariant**: The policy engine refuses automated execution (`HUMAN_REVIEW`). **Zero ExecutionAuthorization is generated.** The execution button is disabled.

#### Step 4: High-Risk Fraud Gating ($P005$)
1. Inspect a transaction flagged with high risk telemetry or prior chargeback history.
2. **Observe**: Even if recoverability score is high, Rule $P005$ gates the transaction to Human Review. **Zero automated actions are permitted against high-risk accounts.**

#### Step 5: Double Recovery & Stopping Caps ($P002$ & $P003$)
1. Filter by **Policy Denied**:
   - Resolved payments evaluate to `DENY (P002_PAYMENT_ALREADY_RESOLVED)`.
   - Payments with $\ge 2$ previous automated attempts evaluate to `DENY (P003_MAX_AUTOMATED_ATTEMPTS)`.
   - Customers with $\ge 2$ prior communications evaluate to `DENY (P007_CUSTOMER_CONTACT_LIMIT)`.

---

### 3:35–4:25 | Benchmark & Honest Tradeoff Discussion
1. Scroll down to the **Holdout Strategy Benchmark** section (50,000 transactions across Seeds 101–505):
   - **`NO_ACTION`**: ₹71,342.40 (0.96% natural recovery).
   - **`NAIVE_RETRY`**: ₹809,172.38 (10.85% recovery rate; 24.83% precision).
   - **`RULE_BASED`**: ₹3,626,512.01 (Unconstrained heuristic; 48.61% recovery rate).
   - **`REVIVE`**: ₹2,726,857.62 (**₹2,655,515.22 in incremental revenue**; **56.04% precision**).
2. **Explain the Tradeoff Proactively**:
   - `RULE_BASED` achieved higher gross recovery because it operated with zero constraints (retrying high-risk accounts, ignoring fatigue limits).
   - `REVIVE` recovered **75.19% of RULE_BASED volume** while reducing merchant interventions by **22.37%**, capping automated attempts at 2, and allowing **zero automated high-risk leaks**.

---

### 4:25–5:00 | Auditability & Limitations Summary
1. Click **Inspect Trace / Audit Log** to demonstrate full chronological decision traceability.
2. Conclude with explicit scope boundaries:
   - Evaluated within a rigorous synthetic lifecycle simulator.
   - Production readiness requires live gateway webhook integration, merchant authentication, and canary A/B validation on live merchant traffic.

---

## 3. Server Clean Shutdown
Press `Ctrl+C` in the terminal running `server.cli` to terminate the server.
