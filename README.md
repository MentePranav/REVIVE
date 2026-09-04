# REVIVE

## Autonomous Revenue Recovery Decision System

> **Recover more revenue. Intervene less. Stay in control.**

REVIVE is a simulation-based autonomous revenue recovery decision system for failed-payment recovery. It analyzes transaction context, diagnoses the likely failure mode, estimates recoverability, recommends an action, and routes that recommendation through explicit policy and safety gates before simulated execution.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Tests Passing](https://img.shields.io/badge/tests-243%20passed-brightgreen.svg)]()
[![Governance](https://img.shields.io/badge/Governance-Fail--Closed-red.svg)]()
[![Environment Scope](https://img.shields.io/badge/Environment-Synthetic%20Simulation-purple.svg)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

> [!NOTE]
> **Synthetic Evaluation Environment**
> **Simulation-only prototype.** No real payments, customer data, or live payment credentials are used. All monetary amounts, transaction histories, and recovery statistics in this repository are synthetic evaluation outputs generated in a controlled benchmark environment.

---

## What REVIVE Does

REVIVE transforms payment failure and checkout drop-off recovery from unconstrained, high-friction scripts into a **deterministic, interpretable contextual decision system with governed execution**.

Rather than blindly retrying every failure or blasting uncoordinated customer reminders, REVIVE:
1. **Diagnoses the root cause** using multi-factor telemetry (error codes, customer history, payment method, retry count).
2. **Estimates recoverability ($P_{rec}$)** and calculates Net Expected Value ($EV = P_{rec} \cdot \text{Amount} - \text{Cost} - \text{Friction}$) across candidate actions (`RETRY`, `REMINDER`, `PAYMENT_LINK`, `DO_NOTHING`).
3. **Enforces institutional safety policies** ($P001$–$P010$) before any action can occur.
4. **Executes only authorized actions** via a validated `ExecutionAuthorization` issued only after policy gates pass.
5. **Maintains a complete audit trail** with immutable decision traces and correlation IDs.

---

## Why This Problem Matters

Payment failures and checkout drop-offs cause substantial revenue leakage in digital commerce. However, automated recovery carries serious operational risks when unconstrained:

- **Issuer Friction**: Repeatedly firing payment retries against exhausted cards or permanent declines damages merchant reputation, risks issuer throttling, and wastes payment processing fees.
- **Customer Fatigue**: Firing uncoordinated SMS, WhatsApp, and email payment links irritates customers and erodes brand trust.
- **Fraud & Dispute Exposure**: Retrying compromised or high-risk accounts indiscriminately increases fraudulent settlements and chargeback liabilities.
- **Lack of Institutional Governance**: Most recovery setups run ad-hoc scripts with no stopping caps, no double-recovery guards, and zero decision auditability.

### Why Naive Retries Are Insufficient
Traditional recovery approaches rely on naive heuristics—either retrying every failed transaction immediately or applying static delay rules. These fail because:
1. **They Ignore Failure Semantics**: A technical network timeout requires a retry; an invalid PIN or insufficient funds requires an alternate payment method or payment link; an expired card requires customer re-entry.
2. **They Maximize Interventions Instead of Net Value**: Blindly retrying produces low intervention precision, harassing customers for transactions that would have naturally recovered or cannot be recovered.
3. **They Lack Stopping Rules**: Without strict stopping caps, scripts enter infinite retry loops or bombard customers with redundant messages.

---

## How REVIVE Works

REVIVE follows a closed-loop governed decision-and-action lifecycle:

$$\mathbf{OBSERVE} \longrightarrow \mathbf{DIAGNOSE} \longrightarrow \mathbf{SCORE} \longrightarrow \mathbf{DECIDE} \longrightarrow \mathbf{GOVERN} \longrightarrow \mathbf{EXECUTE} \longrightarrow \mathbf{OBSERVE\ OUTCOME}$$

1. **Observe**: Ingests observable failure telemetry (error code, error source, error step, payment method, amount, customer tenure, and history).
2. **Diagnose**: Classifies failure into a normalized taxonomy (Transient, Authentication, Bank Decline, Insufficient Funds, High Risk) with a calibrated confidence score.
3. **Score & Decide**: Evaluates recoverability probability ($P_{rec}$) and selects the action that maximizes Net Expected Value ($EV$).
4. **Govern**: Evaluates the recommendation against 10 deterministic policy rules ($P001$–$P010$).
5. **Execute**: If policy approves, issues a validated `ExecutionAuthorization` and simulates execution under idempotency locks.
6. **Record**: Logs the entire lifecycle with timestamps, decision reasons, and trace identifiers to an immutable audit trail.

---

## Architecture

REVIVE separates intelligence from execution through an explicit zero-trust policy boundary:

```text
       [ Synthetic Transaction / Failed Checkout ]
                           │
                           ▼
               [ Feature Extraction Layer ]
                           │
                           ▼
               [ Contextual Diagnosis Engine ]
                           │
                           ▼
          [ Recoverability & Action Scoring Engine ]
                           │
                           ▼
              ┌───────────────────────────┐
              │   Policy & Safety Gate    │◄─── Zero-Trust Policy Rules (P001-P010)
              │ (Stop Caps, Risk, Limits) │
              └─────────────┬─────────────┘
                            │
               [ ExecutionAuthorization Token ]
                            │
                            ▼
             [ Controlled Execution Simulator ]
                            │
                            ▼
                    [ Synthetic Outcome ]
                            │
                            ▼
              [ Immutable Audit Trail & Metrics ]
```

### The Critical Security Boundary
**The recommendation layer cannot directly execute an action.** Automated execution requires a validated `ExecutionAuthorization` issued only after policy gates pass. If policy denies or escalates an action, zero execution occurs.

---

## Decision Intelligence

REVIVE uses a **deterministic, interpretable contextual decision engine** rather than an opaque generative AI model:

- **Feature Extraction**: Extracts 30+ domain features across failure telemetry, customer behavioral profile, payment method reliability, and retry history.
- **Root-Cause Diagnosis**: Classifies failures into normalized categories (`TRANSIENT`, `AUTHENTICATION`, `BANK_DECLINE`, `INSUFFICIENT_FUNDS`, `HIGH_RISK`) with calibrated confidence.
- **Recoverability Estimation ($P_{rec}$)**: Generates a calibrated recovery probability ($P_{rec} \in [0, 1]$) based on contextual signals.
- **Net Expected Value ($EV$) Optimization**: Evaluates candidate actions (`RETRY`, `REMINDER`, `PAYMENT_LINK`, `DO_NOTHING`):
  $$EV(\text{Action}) = P_{rec}(\text{Action}) \cdot \text{Amount} - \text{Cost}(\text{Action}) - \text{Friction}(\text{Action})$$
- **Explainability**: Every decision outputs human-readable top positive/negative feature contributions and decision rationale.

---

## Policy & Safety Governance

REVIVE enforces **deterministic code safeguards and fail-closed policies** ($P001$–$P010$) before any action can be dispatched:

```text
UNTRUSTED INPUT → CONTEXTUAL INTELLIGENCE → POLICY ENGINE → EXECUTION AUTHORIZATION → CONTROLLED EXECUTOR
```

| Rule ID | Policy Guard Name | Enforced Boundary & Behavior |
| :--- | :--- | :--- |
| **$P001$** | **Input Schema Validation** | Validates amount $> 0$, non-empty customer ID, and valid currency. Rejects malformed payloads. |
| **$P002$** | **Anti-Double Recovery** | Re-validates payment state; blocks execution if payment is already `SUCCESS`, captured, or settled. |
| **$P003$** | **Hard Stopping Cap** | Strictly limits automated recovery attempts to **maximum 2 attempts per payment**. |
| **$P004$** | **Diagnostic Confidence Gate** | If diagnostic confidence $< 85\%$, automated action is blocked and routed to **Human Review**. |
| **$P005$** | **High-Risk Fraud Gate** | High-risk/dispute flags route 100% to **Human Review**. **Zero automated interventions allowed.** |
| **$P006$** | **Action Allowlist** | Strictly permits only enumerated actions (`RETRY`, `REMINDER`, `PAYMENT_LINK`, `DO_NOTHING`). |
| **$P007$** | **Contact Fatigue Limits** | Limits customer communications (reminders/links) to **maximum 2 contacts per customer**. |
| **$P008$** | **Cooldown Enforcement** | Mandatory 300-second pause between automated interventions on the same transaction. |
| **$P009$** | **Template Whitelist** | All customer messages must use approved, registered templates from `ApprovedTemplateRegistry`. |
| **$P010$** | **Execution Authorization** | Generates an immutable, validated `ExecutionAuthorization` strictly when all safety gates pass. |

---

## Controlled Execution

The **Controlled Execution Simulator** enforces state-aware safeguards at the point of simulated dispatch:

- **Token Validation**: Re-checks that `ExecutionAuthorization` exists, is valid, matches the target customer/payment ID, and has not expired.
- **Live State Re-Validation**: Re-checks live payment status immediately before simulation to ensure no out-of-band capture occurred.
- **Idempotency Locks**: SHA-256 idempotency cache ensures at most 1 execution per unique authorization key, preventing duplicate actions even under rapid concurrent requests.
- **Fail-Closed Architecture**: Any internal error, missing authorization, or unhandled exception immediately aborts execution and records an audit event.

---

## Evaluation

REVIVE was scientifically evaluated using a rigorous multi-seed holdout evaluation framework:

- **Development Set (Tuning & Thresholds)**: Seed `42` (2,000 transactions).
- **Evaluation Holdout Sets**: 5 unseen holdout seeds (`[101, 202, 303, 404, 505]`) with 10,000 transactions each (**50,000 total holdout transactions**).
- **Strict Leakage Isolation**: Ground-truth counterfactual matrices are evaluated strictly after simulated action dispatch. Zero ground-truth features enter the diagnosis or policy engines.
- **Statistical Rigor**: Non-parametric bootstrap resampling (1,000 iterations) at 95% confidence intervals, Brier score probability calibration (`0.2549`), and Expected Calibration Error (`25.37%`).

---

## Benchmark Results

Evaluated across **5 unseen holdout seeds** (Seeds 101, 202, 303, 404, 505) with 10,000 transactions per seed (50,000 total transactions):

| Strategy | Mean Recovered Revenue | Mean Incremental Revenue ($\Delta R$) | Recovery Rate (Failed Opps) | Interventions per 10k | Intervention Precision | Human Review Escalation | High-Risk Leaks |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`NO_ACTION`** | ₹71,342.40 | ₹0.00 | 0.94% | 0 | N/A | 0 | 0 |
| **`NAIVE_RETRY`** | ₹809,172.38 | ₹737,829.97 | 10.86% | 1,342.4 | 30.84% | 0 | 18 |
| **`RULE_BASED`** | ₹3,626,512.01 | ₹3,555,169.60 | 48.58% | 1,690.0 | 69.46% | 0 | 29 |
| **`REVIVE`** *(Governed)* | **₹2,726,857.62** | **₹2,655,515.22** | **36.53%** | **1,312.0** | **56.04%** | **624 (5.64%)** | **0** |

*All benchmark figures reflect synthetic simulation results in a controlled evaluation environment.*

---

## Key Tradeoff

In the synthetic benchmark, **`RULE_BASED` achieved higher gross recovery (₹3,626,512.01) than REVIVE (₹2,726,857.62).**

This is not a defect—it is the deliberate consequence of institutional safety boundaries:
1. **Unconstrained vs. Governed**: `RULE_BASED` is an unconstrained heuristic that fired 28.8% more interventions (1,690.0 vs 1,312.0 per 10k), retried high-risk transactions without restriction, and ignored customer contact cooldowns.
2. **Safety Boundary Enforcement**: REVIVE achieved **₹2,655,515.22 in incremental revenue over `NO_ACTION`** (recovering 75.19% of `RULE_BASED` gross revenue) while:
   - Reducing merchant interventions by **22.37%** (378 fewer interventions per 10k transactions).
   - Enforcing a strict **2-attempt maximum ceiling** ($P003$).
   - Permitting **zero automated high-risk actions** ($P005$), routing 100% of suspicious cases to Human Review.
   - Escalating **624 uncertain cases (5.64% of 11,064 failed opportunities)** to Human Review rather than taking uncalibrated risks.

> **Core Finding**: `RULE_BASED` achieves higher gross recovery in the synthetic benchmark through more aggressive intervention. REVIVE deliberately trades some gross recovery for fewer interventions and explicit safety governance.

---

## Interactive Control Center

REVIVE includes an interactive, single-page web application Control Center served directly by FastAPI:

- **KPI Overview**: Real-time summary cards (Revenue at Risk, Recovered Revenue, Incremental Revenue, Recovery Rate, Interventions, Safety Blocks).
- **Recovery Cases Queue**: Filterable and sortable table of failed opportunities with live search and drilldown modals.
- **Explainability & Safety Drilldown**: Inspects failure telemetry, feature attributions, Expected Value ranking, and pass/fail safety rule checklist ($P001$–$P010$) for any individual transaction.
- **Interactive Execution**: Allows single-case simulated execution with live state validation, idempotency token check, and simulated outcome recording.
- **Safety & Governance Dashboard**: Visual overview of rule hierarchies and active safety counters.
- **Comparative Benchmark View**: Dynamic matrix comparing `NO_ACTION`, `NAIVE_RETRY`, `RULE_BASED`, and `REVIVE`.
- **Immutable Audit Trail**: Chronological explorer of all audit events with trace IDs.

---

## Run Locally

REVIVE runs 100% locally with zero external network or cloud dependencies.

### Prerequisites
- Python 3.10, 3.11, or 3.12
- Git

### Setup & Launch

```bash
# 1. Clone repository
git clone https://github.com/MentePranav/REVIVE.git
cd REVIVE

# 2. Create and activate virtual environment
# On Windows:
python -m venv .venv
.\.venv\Scripts\activate

# On macOS / Linux:
python3 -m venv .venv
source .venv/bin/activate

# 3. Install minimal dependencies
pip install -r requirements.txt

# 4. Launch the Interactive Control Center
python -m server.cli --port 8000
# Or on Windows, double-click: start_revive.bat
```

Open your browser at: **`http://localhost:8000`** (or **`http://localhost:8000/control-center`** for the Control Center)
Interactive OpenAPI / Swagger documentation is available at: **`http://localhost:8000/docs`**

---

## Testing

Run the complete 243-test regression, security hardening, and adversarial validation suite:

```bash
# Run all unit, integration, property, adversarial, and public security tests
pytest tests/ -v

# Run public security and authorization regression tests
pytest tests/test_public_security.py -v

# Run adversarial red-team penetration tests (69 attack scenarios)
pytest tests/test_red_team_adversarial.py tests/test_adversarial_hardening.py -v
```

All 243 tests execute deterministically in ~10–15 seconds with zero external network calls.

---

## Deployment & Production Configuration

REVIVE can be hosted as a lightweight web service on any container platform or cloud application runner (e.g., Render, Railway, Cloud Run, AWS App Runner, Docker).

### 1. Production Startup Command
The application runs as a standard ASGI service via Uvicorn:
```bash
python -m uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8000}
```
Or via the built-in CLI launcher (which automatically detects the `PORT` environment variable):
```bash
python -m server.cli
```

### 2. Environment Variables & Configuration
| Variable | Purpose | Default | Recommended Production Value |
|---|---|---|---|
| `PORT` | HTTP port to bind | `8000` | Injected by hosting platform |
| `HOST` | Interface to bind | `127.0.0.1` (`0.0.0.0` if `PORT` set) | `0.0.0.0` |
| `APP_ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins | `*` | Specific domain (e.g. `https://your-domain.com`) |
| `APP_RATE_LIMIT_ENABLED` | Enable sliding-window rate limiting | `true` | `true` |
| `APP_SECURITY_HEADERS_ENABLED` | Injects CSP, HSTS, frame protection | `true` | `true` |
| `LOG_LEVEL` | Application logging verbosity | `INFO` | `INFO` |

### 3. Health Check
Hosting platforms can use the lightweight health endpoint:
- **Path:** `/api/health`
- **Method:** `GET`
- **Expected Status:** `200 OK`
- **Payload:** Returns service status, version metadata, and reproducibility SHA-256 fingerprint without triggering any simulations.

### 4. Architectural Boundaries & State Model
- **Single-Process In-Memory State:** All simulation sessions and case details are maintained in memory. Restarting the process resets the runtime state to the golden benchmark baseline.
- **In-Process Rate Limiter:** The sliding-window rate limiter runs in-process per worker. Distributed horizontal scaling would require external state storage (e.g., Redis).
- **Same-Origin Delivery:** Frontend assets and backend API are served from the same origin, eliminating cross-origin browser issues.
- **Zero Secrets Required:** No payment credentials, database connection strings, or external API keys are needed.

---

## Project Structure

```text
REVIVE/
├── agent/                  # Contextual intelligence: Diagnosis, feature extraction, scoring
│   ├── diagnostician.py    # Failure taxonomy & root-cause diagnosis
│   ├── recoverability.py   # Calibrated recovery probability estimation
│   ├── action_scorer.py    # Net Expected Value (EV) calculation across actions
│   ├── recommender.py      # Recommendation synthesis with explainability
│   └── models.py           # Pydantic schemas (DiagnosisResult, ReviveRecommendation)
├── policy/                 # Policy, Safety & Governance Engine
│   ├── engine.py           # Rule evaluator & safety checklist (P001-P010)
│   ├── config.py           # Safety thresholds, cooldowns, attempt caps, template registry
│   ├── state_context.py    # State contexts (PaymentStateContext, CustomerStateContext)
│   └── models.py           # PolicyDecision, ExecutionAuthorization tokens
├── execution/              # Controlled recovery execution simulator
│   ├── executor.py         # State-aware simulated dispatcher with idempotency locks
│   ├── orchestrator.py     # End-to-end event lifecycle orchestrator
│   ├── batch.py            # Batch execution runner
│   └── models.py           # ExecutionStatus, SimulatedRecoveryOutcome, ExecutionAuditEvent
├── simulator/              # Synthetic payment & customer lifecycle generator
│   ├── transaction_generator.py # Transaction & checkout drop generator
│   ├── customer_generator.py    # Customer behavioral profiles & payment instruments
│   ├── ground_truth_engine.py   # Counterfactual outcome simulator (isolated)
│   └── public_schema.py         # Observable event schemas
├── evaluation/             # Multi-seed experimental benchmark engine
│   ├── experiment/         # Runner, calibration, claim guardrails, dataset splitter
│   ├── strategies/         # Baseline strategies (NO_ACTION, NAIVE_RETRY, RULE_BASED, REVIVE)
│   └── metrics.py          # Precision, recovery rate, financial accounting checks
├── server/                 # Interactive Control Center backend & frontend
│   ├── app.py              # FastAPI application with REST endpoints & correlation IDs
│   ├── state.py            # In-memory session coordinator
│   ├── models.py           # REST request/response schemas
│   ├── rate_limiter.py     # Sliding-window rate limiter & abuse protection
│   └── static/             # Vanilla HTML5 / CSS3 / ES6 Single-Page Application UI
├── tests/                  # 243 automated unit, integration, security, and adversarial tests
├── docs/                   # Full documentation suite and architectural specifications
├── start_revive.bat        # 1-click Windows startup script
├── .env.example            # Environment configuration template
├── requirements.txt        # Production dependency specifications
└── README.md               # Project documentation
```

---

## Limitations

- **Synthetic Simulation**: All transactions, failure distributions, customer behaviors, and recovery outcomes are generated using a controlled synthetic simulator.
- **Production Pre-requisites**: Real-world production deployment requires integrating live payment gateway webhooks, merchant API credentials, distributed messaging queues (e.g., Kafka/Redis), and canary rollouts on live merchant traffic.
- **Cardholder Behavior**: Real-world customer response rates to payment links and reminders may vary from simulated distributions.
- **Evaluation Benchmark**: The canonical 50,000-transaction benchmark is a controlled synthetic evaluation demonstrating algorithmic recovery tradeoffs, not a live production performance claim.

---

## Project Status

REVIVE is currently a simulation-based research and prototype system demonstrating governed autonomous revenue recovery. It operates 100% locally with zero external network or cloud dependencies.

---

## License

Licensed under the [Apache License, Version 2.0](LICENSE).
