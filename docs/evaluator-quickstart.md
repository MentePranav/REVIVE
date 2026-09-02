# REVIVE — Evaluator Quickstart Guide

**Target Evaluation Time:** 3–5 Minutes  
**Track:** Track 3: AI Revenue Recovery — Razorpay AI Buildathon 2026  
**Environment:** 100% Local & Self-Contained (Zero API Keys or Cloud Credentials Required)

---

## 1. Prerequisites
- **Python:** Version 3.10, 3.11, or 3.12
- **Git:** Installed and available in PATH
- **Web Browser:** Any modern browser (Chrome, Edge, Firefox, Safari)

---

## 2. Step-by-Step Installation

### Step 2.1: Clone the Repository
```bash
git clone https://github.com/your-username/REVIVE.git
cd REVIVE
```

### Step 2.2: Create and Activate Virtual Environment
**On Windows (PowerShell / Command Prompt):**
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

**On macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2.3: Install Dependencies
```bash
pip install -r requirements.txt
```
*(Installation takes ~15–30 seconds. No heavy ML frameworks or proprietary cloud SDKs required.)*

---

## 3. Start the Interactive Control Center

**Option A: 1-Click Startup (Windows)**
Double-click `start_revive.bat` or run:
```cmd
start_revive.bat
```

**Option B: Universal Command Line (All Platforms)**
```bash
python -m server.cli --port 8000 --host 127.0.0.1
```

Once started, open your browser and navigate to:
👉 **`http://localhost:8000`**

*(API Swagger docs are also available at `http://localhost:8000/docs`)*

---

## 4. 5-Minute Evaluator Tour

### Step 4.1: Inspect Overview Metrics
On the top header and metric cards, observe:
- **Revenue at Risk:** Total potential revenue from failed payments and abandoned checkouts.
- **Recovered Revenue:** Revenue recovered through simulated authorized interventions.
- **Incremental Revenue:** Net revenue gained above the natural recovery baseline (`NO_ACTION`).
- **Intervention Precision:** Percentage of automated interventions that resulted in successful recovery.

### Step 4.2: Inspect a Recoverable Transaction (Policy Approved)
1. In the **Recovery Cases Table**, look for a transaction with **Policy Decision: `ALLOW`** (e.g. `txn_00000066`).
2. Click **"Inspect"** to view the **Diagnosis Modal**:
   - **Root-Cause Diagnosis:** (e.g., Transient Network Timeout or Insufficient Balance).
   - **Recoverability Score:** Calibrated probability ($P_{rec}$) and expected value breakdown.
   - **Recommended Action:** (e.g., `PAYMENT_LINK` or `RETRY`).
   - **Policy Evaluation Trace:** Shows all 10 rules ($P001$–$P010$) validated with pass checks.
   - **Execution Authorization:** Shows the validated ExecutionAuthorization issued only after policy gates pass.

### Step 4.3: Execute a Live Simulated Action
1. On any case with **Status: `ACTION_AUTHORIZED`**, click the **"Execute Action"** button.
2. Observe the instant simulated execution:
   - State re-validation ensures the payment is not already captured.
   - Idempotency key is locked.
   - Outcome is simulated deterministically from the underlying lifecycle engine.
   - The case updates to **Status: `EXECUTED`** with a green badge.

### Step 4.4: Inspect a Governed Safety Gate (Blocked / Human Review)
1. In the status filter dropdown, select **`HUMAN_REVIEW_REQUIRED`**.
2. Click **"Inspect"** on a case with **Primary Rule: `P004_LOW_DIAGNOSIS_CONFIDENCE`** or **`P005_HIGH_RISK_GATE`**:
   - Observe that the intelligence engine's recommendation was **NOT** executed.
   - Notice that **Zero ExecutionAuthorization** was generated.
   - The case was safely escalated to Human Review to prevent customer harassment or fraud losses.

### Step 4.5: Inspect the 50,000-Transaction Comparative Benchmark
1. Scroll down to the **"Holdout Strategy Benchmark"** section.
2. Compare the 4 strategies across the 5 holdout seeds (50,000 transactions):
   - `NO_ACTION`: Natural recovery baseline (₹71,342.40).
   - `NAIVE_RETRY`: Blind retry baseline (₹809,172.38).
   - `RULE_BASED`: Unconstrained heuristic (₹3,626,512.01).
   - `REVIVE`: Governed system (₹2,726,857.62, ₹2.65M incremental over NO_ACTION with 22.4% fewer interventions and 0 high-risk leaks).

---

## 5. Running Automated Tests

Run the full 226-test automated test suite:
```bash
pytest tests/ -v
```
**Expected Result:** 226 passed in ~9–11 seconds (100% green).

Run the dedicated adversarial red-team penetration suite:
```bash
pytest tests/test_red_team_adversarial.py -v
```
**Expected Result:** 49 passed in ~1 second.

---

## 6. Verifying Health & Reproducibility API

To verify the system's runtime health and deterministic fingerprint via CLI:
```bash
curl http://127.0.0.1:8000/api/health
```

**Expected JSON Response:**
```json
{
  "status": "healthy",
  "service": "REVIVE — Autonomous Revenue Recovery",
  "application_version": "1.0.0",
  "mode": "synthetic_simulation_benchmark",
  "reproducibility_fingerprint": "35b2e65d2efaa521",
  "environment_valid": true
}
```

---

## 7. Troubleshooting
- **Port 8000 in use:** Start on another port with `python -m server.cli --port 8080`.
- **Reset Demo State:** Click the **"Reset Demo (Seed 42)"** button in the dashboard top navigation bar, or call `POST http://127.0.0.1:8000/api/demo/reset`.
