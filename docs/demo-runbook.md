# REVIVE — Evaluator Demo Runbook & Step-by-Step Guide

This runbook allows any evaluator or developer to run and verify the REVIVE Control Center locally in under 5 minutes without prior knowledge of the codebase.

---

## 1. Prerequisites & Startup

### Option A: Windows One-Click Launcher
Double-click `start_revive.bat` in the repository root directory.

### Option B: Terminal Command
```powershell
# From the repository root
.\.venv\Scripts\python.exe -m server.cli --port 8000 --host 127.0.0.1
```

### Verification & Health Check
Open your browser to: **[http://localhost:8000/api/health](http://localhost:8000/api/health)**
- Expected JSON response: `"status": "healthy"`, `"reproducibility_fingerprint": "35b2e65d2efaa521"`, `"environment_valid": true`.

Open the Web UI: **[http://localhost:8000](http://localhost:8000)**

---

## 2. Five-Minute Evaluator Demo Script

### Step 1: Default Golden Session Initialization
1. Click **🔄 Reset Demo** in the top navigation bar.
2. **Observe**: The application reloads into the deterministic default Golden State (**Seed 42, 100 Transactions**).
3. **Check Top KPIs**:
   - **Revenue At Risk**: Displays total synthetic failed volume.
   - **Incremental Revenue (ΔR)**: Shows net revenue recovered above baseline.
   - **Safety Blocks**: Displays interventions prevented by the Zero-Trust Policy Engine.

---

### Step 2: The 5 Core Verification Scenarios

Switch to the **Recovery Cases** tab in the navigation bar.

#### Scenario A: Intelligent Successful Recovery (Transient Gateway Timeout)
1. In the search box, enter `TRANSIENT` or look for a case with `Recommended Action: RETRY`.
2. Click **Inspect** on the case.
3. **Observe**:
   - **Intelligence**: Model reports high confidence ($\ge 90\%$) and high recoverability score.
   - **Safety Gate**: All 7 rules show green checkmarks $[✓]$, and policy decision is `ALLOW (P010_ACTION_APPROVED)`.
   - **Authorization Token**: A cryptographic `ExecutionAuthorization` token (`auth_...`) is generated.
4. Click **⚡ Execute Simulated Recovery**.
5. **Observe**: Execution status transitions to `EXECUTED`, outcome changes to `RECOVERED`, and a synthetic reference (`sim_ret_...`) is logged.

#### Scenario B: Already-Resolved Payment Block (P002 Double-Recovery Guard)
1. Attempt to execute recovery on an already-settled case or inspect an event with `is_already_resolved = True`.
2. **Observe**: Policy decision evaluates to `DENY (P002_PAYMENT_ALREADY_RESOLVED)`.
3. **Safety Invariant**: No execution authorization token is created. The execution button is disabled.

#### Scenario C: Low Diagnostic Confidence Escalation (P004 Human Review Gate)
1. Filter the status dropdown by **Human Review** or search for an ambiguous failure category.
2. Click **Inspect**.
3. **Observe**:
   - Model confidence is below the $85\%$ threshold.
   - Policy decision is `HUMAN_REVIEW (P004_LOW_DIAGNOSIS_CONFIDENCE)`.
   - **Safety Invariant**: The system refuses automated intervention and routes the case to human operators.

#### Scenario D: Attempt Cap & Fatigue Limit Blocks (P003 & P007)
1. Filter by `Policy Blocked` or look for cases with prior attempt history.
2. **Observe**:
   - Cases with 2 previous attempts display `DENY (P003_MAX_AUTOMATED_ATTEMPTS)`.
   - Cases exceeding 2 customer communications display `DENY (P007_CUSTOMER_CONTACT_LIMIT)`.

#### Scenario E: Idempotency & Double-Click Protection
1. Open any approved case.
2. Rapidly double-click the **⚡ Execute Simulated Recovery** button.
3. **Observe**:
   - The button disables instantly on the first click to prevent duplicate submissions.
   - The backend checks the SHA-256 idempotency cache (`execution_cache`), ensuring exactly **one** recovery outcome is recorded.

---

### Step 3: Benchmarks & Multi-Seed Holdout Verification
1. Click the **Benchmark** tab in the navigation bar.
2. **Observe**: The 4-way comparative table across 50,000 holdout transactions (Seeds 101–505).
3. Confirm that REVIVE captures **INR 2,655,515.22 in incremental revenue** while maintaining zero high-risk fraud leaks.

---

### Step 4: Audit Trail Inspection
1. Click the **Audit Log** tab.
2. **Observe**: The live, immutable chronological event stream logging `REQUESTED`, `AUTHORIZATION_VALIDATED`, `EXECUTED`, and `OUTCOME_RECORDED` with timestamped correlation IDs.

---

## 3. Server Shutdown
Press `Ctrl+C` in the terminal window running `server.cli` to cleanly terminate the process.
