# REVIVE

**A Governed Autonomous Revenue Recovery Decision-and-Execution System**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Tests Passing](https://img.shields.io/badge/tests-226%20passed-brightgreen.svg)]()
[![Zero-Trust Safety](https://img.shields.io/badge/Safety-Zero--Trust%20Fail--Closed-red.svg)]()
[![Environment Scope](https://img.shields.io/badge/Environment-Synthetic%20Simulation-purple.svg)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

> *"Recover revenue intelligently. Intervene selectively. Enforce institutional safety boundaries."*

---

## 1. Project Name & Description
**REVIVE** is an autonomous revenue recovery decision-and-execution system designed for digital commerce and payment aggregators. It transforms failed payment and abandoned checkout recovery from unconstrained, high-friction scripts into a **deterministic, interpretable contextual decision system with governed execution**.

---

## 2. The Problem
Payment failures and checkout drop-offs cause substantial revenue leakage in digital commerce. However, handling payment failures is fraught with operational risk:
- **Issuer Friction**: Repeatedly firing payment retries against exhausted cards or permanent issuer declines damages merchant reputation, risks issuer throttling, and wastes processing fees.
- **Customer Fatigue**: Firing uncoordinated SMS, WhatsApp, and email payment links irritates customers and erodes brand trust.
- **Fraud & Chargeback Exposure**: Retrying compromised or high-risk accounts indiscriminately increases fraudulent settlements and chargeback liabilities.
- **Lack of Institutional Governance**: Most recovery setups run ad-hoc scripts with no stopping caps, no double-recovery guards, and zero decision auditability.

---

## 3. Why Naive Retries Are Insufficient
Traditional recovery approaches rely on naive heuristics—either retrying every failed transaction immediately or applying simple static delay rules. These fail because:
1. **They Ignore Failure Semantics**: A technical network timeout requires a retry; an invalid PIN or insufficient funds requires an alternate payment method or payment link; an expired card requires customer re-entry.
2. **They Maximize Interventions Instead of Net Value**: Blindly retrying produces low intervention precision, harassing customers for transactions that would have naturally recovered or cannot be recovered.
3. **They Lack Stopping Rules**: Without strict stopping caps, scripts enter infinite retry loops or bombard customers with redundant messages.

---

## 4. The REVIVE Solution
REVIVE does not blindly retry failed payments. Instead, it follows a closed-loop governed lifecycle:
1. **Diagnoses the root cause** using multi-factor telemetry (error codes, customer history, payment method, retry count).
2. **Estimates recoverability ($P_{rec}$)** and calculates Net Expected Value ($EV = P_{rec} \cdot \text{Amount} - \text{Cost} - \text{Friction}$) across actions (`RETRY`, `REMINDER`, `PAYMENT_LINK`, `DO_NOTHING`).
3. **Enforces institutional safety policies** ($P001$–$P010$) before any action can occur.
4. **Executes only authorized actions** via a cryptographically bound `ExecutionAuthorization` token.
5. **Maintains a complete audit trail** with immutable decision traces and correlation IDs.

---

## 5. Architecture
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
               [ Execution Authorization Token ]
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

### The Autonomous Decision Loop
$$\mathbf{OBSERVE} \longrightarrow \mathbf{DIAGNOSE} \longrightarrow \mathbf{SCORE} \longrightarrow \mathbf{DECIDE} \longrightarrow \mathbf{GOVERN} \longrightarrow \mathbf{EXECUTE} \longrightarrow \mathbf{OBSERVE\ OUTCOME}$$

---

## 6. Safety & Governance Model ($P001$–$P010$)
REVIVE enforces an absolute architectural invariant: **A recommendation is never authorization.**

```text
UNTRUSTED INPUT → REVIVE INTELLIGENCE → POLICY ENGINE → EXECUTION AUTHORIZATION → CONTROLLED EXECUTOR
```

Key Policy Safeguards:
- **$P001$ (Input Validation)**: Validates amount $> 0$, non-empty customer ID, valid currency.
- **$P002$ (Anti-Double Recovery)**: Blocks recovery if payment is already `SUCCESS` or resolved.
- **$P003$ (Hard Stopping Cap)**: Max 2 automated attempts per payment. Strictly enforced.
- **$P004$ (Confidence Gate)**: Low diagnostic confidence ($< 85\%$) routes to Human Review.
- **$P005$ (High-Risk Fraud Gate)**: High risk or chargeback history routes to Human Review. **Zero automated actions permitted.**
- **$P006$ (Action Allowlist)**: Rejects arbitrary or un-enumerated actions.
- **$P007$ (Contact Fatigue Limit)**: Max 2 communications per customer.
- **$P008$ (Cooldown Enforcement)**: Minimum 300-second interval between automated attempts.
- **$P009$ (Template Whitelist)**: Only approved, registered communication templates allowed.
- **$P010$ (Execution Authorization)**: Issues immutable token only when all rules pass.

---

## 7. Benchmark Results (50,000 Holdout Transactions)
Evaluated across **5 unseen holdout seeds** (Seeds 101, 202, 303, 404, 505) with 10,000 transactions per seed (50,000 total):

| Strategy | Mean Recovered Revenue | Overall Recovery Rate | Interventions per 10k | Intervention Precision | Human Review Escalation | High-Risk Leaks |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`NO_ACTION`** | ₹71,342.40 | 0.96% | 0 | 0.00% | 0 | 0 |
| **`NAIVE_RETRY`** | ₹809,172.38 | 10.85% | 1,023 | 24.83% | 0 | 18 |
| **`RULE_BASED`** | ₹3,626,512.01 | 48.61% | 1,689 | 64.00% | 0 | 29 |
| **`REVIVE`** *(Governed)* | **₹2,726,857.62** | **36.53%** | **1,311** | **56.04%** | **624 (5.64%)** | **0** |

*All benchmark results are synthetic simulation results and do not represent live Razorpay production performance.*

---

## 8. Honest Benchmark Tradeoff
In this simulation, **`RULE_BASED` achieved higher gross recovery (₹3,626,512.01) than REVIVE (₹2,726,857.62).** 

This is not a defect—it is the deliberate consequence of institutional safety boundaries:
1. **Unconstrained vs. Governed**: `RULE_BASED` is an unconstrained heuristic that fired 28.8% more interventions (1,689 vs 1,311 per 10k), retried high-risk transactions without restriction, and ignored contact cooldowns.
2. **Safety Boundary Enforcement**: REVIVE achieved **₹2,655,515.22 in incremental revenue over `NO_ACTION`** while:
   - Reducing merchant interventions by **22.37%** (378 fewer interventions per 10k transactions).
   - Enforcing a strict **2-attempt maximum ceiling** ($P003$).
   - Permitting **zero automated high-risk actions** ($P005$), routing 100% of suspicious cases to Human Review.
   - Escalating **624 uncertain cases (5.64%)** to Human Review rather than taking uncalibrated risks.

REVIVE is designed for enterprise merchants who need substantial revenue recovery without unbounded operational risk.

---

## 9. Reproducibility & Determinism
REVIVE is 100% locally deterministic and offline-executable:
- **Reproducibility Fingerprint**: SHA-256 configuration digest `35b2e65d2efaa521`.
- **Seed Consistency**: Running any seed (e.g. Seed 42 or Holdout 101) produces identical byte-level outputs, decision scores, and audit traces across runs.
- **Zero Flakiness**: 226/226 automated tests pass deterministically.

---

## 10. Quickstart

### Prerequisites
- Python 3.10, 3.11, or 3.12
- Git

### Setup & Run (Zero External Dependencies)
```bash
# 1. Clone repository
git clone https://github.com/your-username/REVIVE.git
cd REVIVE

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start Control Center
python -m server.cli --port 8000
# Or on Windows, double-click: start_revive.bat
```

Open your browser at: **`http://localhost:8000`**

---

## 11. Demo Instructions (5-Minute Tour)
1. **Load Dashboard (`http://localhost:8000`)**: Observe high-level metrics (Revenue at Risk, Recovered Revenue, Precision).
2. **Inspect Recovery Cases Table**: Examine individual failed transactions with root-cause diagnoses, recoverability tiers, and recommended actions.
3. **Inspect Authorized vs. Blocked Cases**:
   - Filter by `ACTION_AUTHORIZED`: View cases where policy permitted execution.
   - Filter by `HUMAN_REVIEW_REQUIRED`: View cases gated by Low Confidence ($P004$) or High Risk ($P005$).
4. **Trigger Single Case Execution**: Click "Execute Action" on an authorized case to view real-time state validation, idempotency key generation, and simulated outcome.
5. **View Decision & Audit Trail**: Click "Inspect Trace" to inspect the immutable rule evaluation breakdown ($P001$–$P010$).
6. **Inspect Benchmark Comparison**: View the multi-seed comparative benchmark matrix and safety metrics.

---

## 12. Automated Testing
Run the complete 226-test regression and adversarial validation suite:

```bash
# Run all unit, integration, and red-team tests
pytest tests/ -v

# Run only Phase 11 adversarial red-team penetration tests (69 scenarios)
pytest tests/test_red_team_adversarial.py tests/test_adversarial_hardening.py -v
```

---

## 13. Repository Structure
```text
REVIVE/
├── agent/                  # Contextual intelligence: Diagnosis, feature extraction, scoring
│   ├── diagnosis.py        # Failure taxonomy & root-cause diagnosis
│   ├── scoring.py          # Calibrated recoverability scoring & net EV optimization
│   └── models.py           # DiagnosisResult, ReviveRecommendation schemas
├── policy/                 # Policy, Safety & Governance Engine
│   ├── engine.py           # Zero-trust rule evaluator (P001-P010)
│   ├── config.py           # Safety thresholds, cooldowns, and stopping caps
│   └── models.py           # PolicyDecision, ExecutionAuthorization tokens
├── execution/              # Controlled recovery execution simulator
│   ├── executor.py         # State-aware simulated dispatcher with idempotency
│   └── models.py           # ExecutionStatus, SimulatedRecoveryOutcome, AuditEvents
├── simulator/              # Synthetic payment & customer lifecycle generator
│   ├── transaction_generator.py
│   ├── customer_generator.py
│   └── ground_truth_engine.py  # Hidden counterfactual simulation matrix
├── evaluation/             # Multi-seed experimental benchmark engine
│   ├── runner.py           # Comparative evaluation runner across baselines
│   └── metrics.py          # Precision, recovery rate, financial accounting
├── server/                 # Interactive Control Center backend & frontend
│   ├── app.py              # FastAPI REST API & health endpoints
│   ├── state.py            # Local session manager
│   └── static/             # Vanilla HTML5/CSS3/JS Control Center UI
├── tests/                  # 226 unit, integration, and adversarial tests
├── docs/                   # Full documentation suite, architecture, and pitch scripts
├── start_revive.bat        # 1-click Windows startup script
└── requirements.txt        # Minimal pinned dependencies
```

---

## 14. Scope & Limitations (Disclosed)
- **Synthetic Simulation**: All transactions, failure distributions, and recovery outcomes are generated using a controlled synthetic simulator.
- **Production Pre-requisites**: Real-world production deployment requires connecting live Razorpay webhooks, merchant API credentials, distributed message queues (e.g. Kafka/Redis), and canary A/B testing on live merchant traffic.
- **Cardholder Behavior**: Real-world customer response rates to payment links and reminders may vary from simulated distributions.

---

## 15. Future Production Roadmap
1. **Live Gateway Ingestion**: Razorpay webhook ingestion (`payment.failed`, `order.paid`).
2. **Channel Dispatch Integrations**: Official Razorpay Payment Links API, WhatsApp Business API, and SMS gateways.
3. **Online ML Calibration**: Dynamic probability calibration ($P_{rec}$) trained on merchant-specific historical settlement data.
4. **Multi-Tenant Policy Management**: Merchant-customizable policy parameters via dashboard.

---

## 16. Razorpay AI Buildathon 2026 Submission
- **Track**: Track 3 — AI Revenue Recovery
- **Architecture**: Contextual Diagnosis + Policy-Governed Autonomous Execution
- **Zero-Dependency Guarantee**: Fully self-contained local demo; zero external API keys or cloud services required.

---

## 17. License
Licensed under the [Apache License, Version 2.0](LICENSE).
