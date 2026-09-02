# REVIVE

### Autonomous Revenue Recovery Decision System
**Razorpay AI Buildathon 2026 — Track 3: AI Revenue Recovery**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Tests Passing](https://img.shields.io/badge/tests-177%20passed-brightgreen.svg)]()
[![Zero-Trust Safety](https://img.shields.io/badge/Safety-Zero--Trust%20Fail--Closed-red.svg)]()
[![Evaluation Scope](https://img.shields.io/badge/Environment-Synthetic%20Simulation-purple.svg)]()

> *"Recover more revenue. Intervene less. Stay in control."*

---

## 1. The Problem

Payment failures and checkout drop-offs are a leading cause of merchant revenue leakage in digital commerce. However, existing recovery approaches are fundamentally flawed:

- **Blind Retries**: Blindly retrying every failed transaction damages cardholder trust, triggers issuer bank rate limits, and wastes operational budget on permanent bank declines.
- **Communication Spam**: Repeated, uncoordinated customer SMS/WhatsApp reminders cause customer fatigue and brand damage.
- **Risk Exposure**: Indiscriminately attempting to re-bill high-risk or compromised accounts causes chargeback penalties and fraud losses.
- **Lack of Governance**: Traditional scripts lack stopping rules, double-recovery guards, and full decision auditability.

---

## 2. The Idea

> **"REVIVE does not blindly retry failed payments. It diagnoses the failure, estimates recoverability, selects the safest economically useful intervention, enforces policy, executes only authorized actions, and records the complete decision trail."**

REVIVE transforms revenue recovery from an unconstrained script into an **interpretable, policy-governed decision intelligence workflow**.

---

## 3. Why REVIVE Is Different: Governed Recovery vs. Unconstrained Maximization

Most recovery scripts focus solely on unconstrained gross revenue recovery, ignoring operational friction, fraud exposure, and customer harassment. REVIVE explicitly introduces **governed recovery**:

| Feature | Naive Retries / Heuristics | REVIVE Governed Decision System |
| :--- | :--- | :--- |
| **Decision Logic** | Static rules or blind retry | Contextual root-cause diagnosis + Calibrated recoverability scoring |
| **Action Selection** | Always retry or blast reminder | Net Expected Value ($EV = P \cdot Amount - Cost - Friction$) optimization |
| **Safety Governance** | None; unconstrained execution | Zero-trust policy gate ($P001$–$P010$) with cryptographic authorization tokens |
| **Stopping Rules** | Retries until gateway hard error | Hard 2-attempt cap ($P003$) and customer contact limit ($P007$) |
| **Fraud & Risk** | Ignored; acts on all failures | Zero automated intervention on high-risk accounts ($P005$ routes to Human Review) |
| **Double Recovery** | Risks duplicate charges | State-aware: Verifies payment isn't already resolved before execution ($P002$) |
| **Idempotency** | Vulnerable to race conditions | Deterministic SHA-256 idempotency cache prevents duplicate actions |
| **Auditability** | Ephemeral or missing logs | Immutable chronological audit trail with correlation IDs ($X-Correlation-ID$) |

---

## 4. How It Works

![REVIVE Architecture Diagram](docs/revive-architecture.svg)

The system operates across a clean 5-stage lifecycle:
1. **Observable Data Ingestion**: Extracts failed transactions, checkouts, and customer histories (with zero leakage of ground-truth counterfactuals).
2. **Contextual Intelligence**: Diagnoses failure root causes, scores recovery probability ($P_{rec}$), and calculates net Expected Value across `RETRY`, `REMINDER`, `PAYMENT_LINK`, and `DO_NOTHING` using deterministic, interpretable scoring logic (avoiding high-latency external LLM API dependencies).
3. **Zero-Trust Policy Gate**: Evaluates recommendations against 7 strict safety rules ($P001$–$P008$). Only passes issue an immutable `ExecutionAuthorization` token ($P010$).
4. **Controlled Execution Simulator**: Re-validates live payment state, locks idempotency keys, and records simulated recovery outcomes.
5. **Observability & Benchmarking**: Emits structured JSON logs and feeds live metrics into the Interactive Control Center.

---

## 5. Concrete Decision Walkthrough

Here is an actual trace from the REVIVE execution engine:

```text
1. PAYMENT FAILURE EVENT
   - Event ID       : txn_00000104 (Amount: INR 2,499.00, Method: UPI Intent)
   - Error Code     : GATEWAY_ERROR_TIMEOUT ("Bank server did not respond within timeout")
   - Customer State : Tenure: 14 months, Past Success Rate: 92%, Automated Attempts: 0

2. REVIVE CONTEXTUAL INTELLIGENCE
   - Diagnosis      : TRANSIENT_GATEWAY_FAILURE (Confidence: 95.0%, Risk: LOW)
   - Recoverability : 88.4% (High Tier)
   - Expected Value : RETRY (EV: +INR 2,204.12) vs. REMINDER (+INR 840.10) vs. DO_NOTHING (INR 0.00)
   - Recommendation : RETRY

3. ZERO-TRUST POLICY EVALUATION
   - Rule P001 (Schema Valid)             : PASSED [✓]
   - Rule P002 (Payment Not Resolved)     : PASSED [✓]
   - Rule P003 (Attempt Cap < 2)          : PASSED [✓] (Attempt #1)
   - Rule P004 (Diagnostic Confidence)    : PASSED [✓] (95.0% >= 85%)
   - Rule P005 (Fraud & Risk Gate)        : PASSED [✓] (Low Risk)
   - Rule P008 (Cooldown Clear)           : PASSED [✓]
   - Primary Rule Decision                : ALLOW (P010_ACTION_APPROVED)
   - Token Generated                      : auth_7f2b91a0c4

4. CONTROLLED SIMULATED EXECUTION
   - Token Validation                     : Valid & Signed for txn_00000104
   - Idempotency Key                      : b48f12a9c1e089d7 (Stored in Cache)
   - Action Dispatched                    : Simulated Gateway Retry
   - External Ref                         : sim_ret_84a92bc1e0
   - Outcome                              : RECOVERED (Recovered Amount: INR 2,499.00)
   - Audit Event Recorded                 : aud_9f1a0e88c2
```

---

## 6. Safety & Zero-Trust Governance Rules

REVIVE enforces an uncompromised fail-closed safety hierarchy:

- **$P001$ Input Schema Integrity**: Validates currency, positive amounts ($> 0$), and required metadata.
- **$P002$ Payment State Verification**: Prohibits recovery attempts on already captured or settled transactions.
- **$P003$ Hard Attempt Cap**: Strictly caps automated recovery at **2 attempts per payment ID**.
- **$P004$ Diagnostic Confidence Gate**: Actions with model confidence $< 85\%$ are escalated to **Human Review** (624 cases / 5.64% of opportunities in benchmark).
- **$P005$ High-Risk Fraud Gate**: Accounts flagged with risk or chargeback signals route strictly to Risk Review (**0 automated interventions permitted**).
- **$P007$ Contact Fatigue Limits**: Restricts customer reminders/links to a maximum of **2 communications**.
- **$P008$ Cooldown Interval**: Enforces a mandatory **300-second pause** between successive recovery attempts on the same transaction.
- **$P010$ Cryptographic Token Issuance**: Only authorized requests receive an `ExecutionAuthorization` token.

---

## 7. Statistical Benchmark Results (50,000 Holdout Transactions)

> **Notice:** *All metrics reflect a statistically controlled synthetic evaluation benchmark across 5 holdout seeds (Seeds 101, 202, 303, 404, 505) totaling 50,000 transactions and 11,064 failed opportunities. This demonstrates algorithm validity and safety boundaries, not live production Razorpay figures.*

| Strategy | Mean Recovered Revenue (INR) | Mean Incremental Revenue (ΔR) | Recovery Rate | Intervention Precision | Safety Profile & Key Tradeoffs |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`NO_ACTION`** | INR 71,342.40 | INR 0.00 | 0.94% | N/A | Passive baseline; captures organic recoveries only. |
| **`NAIVE_RETRY`** | INR 809,172.38 | INR 737,829.97 | 10.86% | 30.84% | Blindly retries; causes 69.16% failure friction on permanent declines. |
| **`RULE_BASED`** | INR 3,626,512.01 | INR 3,555,169.60 | 48.58% | 69.46% | Unconstrained gross recovery; lacks zero-trust governance & fraud risk gates. |
| **`REVIVE (Governed)`** | **INR 2,726,857.62** | **INR 2,655,515.22** | **36.53%** | **56.04%** | **Governed recovery: 22.4% fewer interventions than RULE_BASED + 2-attempt cap + 0 fraud leaks.** |

### What the Benchmark Taught Us (Constrained vs. Unconstrained Recovery)

In this synthetic simulator, the unconstrained `RULE_BASED` strategy achieved higher gross recovery by aggressively acting across all opportunities without stopping rules or risk boundaries.

**REVIVE deliberately chose not to optimize for unconstrained gross revenue.** Instead:
- REVIVE recovered **INR 2,726,857.62 (75.19% of RULE_BASED gross revenue)**.
- REVIVE achieved this with **378 fewer interventions per 10k transactions (a 22.37% reduction in interventions)**.
- REVIVE delivered **INR 2,655,515.22 in incremental revenue (ΔR)** over passive baseline with **56.04% precision** (vs. 30.84% for naive retry).
- REVIVE escalated **624 ambiguous cases (5.64% of failed opportunities)** to human review and allowed **0 automated interventions on high-risk accounts**.

---

## 8. Quickstart & Demo Instructions

### 1. Launch with One Click (Windows)
```cmd
start_revive.bat
```

### 2. Launch Cross-Platform (CLI)
```bash
# Activate virtual environment
source .venv/bin/activate  # on Windows: .\.venv\Scripts\activate

# Start server
python -m server.cli --port 8000 --host 127.0.0.1
```

### 3. Open Control Center
Navigate to:
- **Interactive Control Center**: [http://localhost:8000](http://localhost:8000)
- **API Documentation (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health & Reproducibility Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

### 4. Run Automated Test Suite
```bash
pytest tests/ -v
```
*(All 177 tests run and pass in ~9.8s)*

---

## 9. Repository Structure

```text
REVIVE/
├── agent/                  # Phase 4: Contextual Feature Extraction, Diagnosis & Scoring
├── baselines/              # Phase 3: NO_ACTION, NAIVE_RETRY, RULE_BASED Baselines
├── core/                   # Phase 9: Config, Error Taxonomy, Logging & Validator
├── docs/                   # Full Documentation, Runbooks, Safety & Evidence Audits
│   ├── architecture.md
│   ├── demo-checklist.md
│   ├── demo-runbook.md
│   ├── evaluator-guide.md
│   ├── evidence-map.md
│   ├── failure-analysis.md
│   ├── final-audit.md
│   ├── final-benchmark-audit.md
│   ├── pitch-script.md
│   ├── red-team-claim-audit.md
│   ├── reliability.md
│   ├── safety-and-governance.md
│   └── submission-checklist.md
├── evaluation/             # Phase 7: Multi-Seed Holdout Experiment Engine
├── execution/              # Phase 6: Controlled Recovery Execution Simulator
├── experiments/            # Phase 7: 50,000 Transaction Benchmark Reports
├── policy/                 # Phase 5: Zero-Trust Safety & Governance Engine
├── server/                 # Phase 8: FastAPI Backend & Single-Page Application UI
│   └── static/             # Frontend Control Center Assets (HTML, CSS, JS)
├── simulator/              # Phase 2: Synthetic Payment & Customer Lifecycle Generator
├── tests/                  # 177 Automated Unit, Integration & Adversarial Tests
├── README.md               # Evaluator-Facing Overview & Benchmark Summary
└── start_revive.bat        # Windows One-Click Demo Launcher
```

---

## 10. Reproducibility & Determinism

Every experiment, session, and simulation run is fully reproducible:
- **Default Golden Demo Seed**: `Seed 42` (100 synthetic transactions).
- **Holdout Evaluation Seeds**: `Seeds 101, 202, 303, 404, 505` (50,000 transactions).
- **Reproducibility Fingerprint**: SHA-256 digest (`35b2e65d2efaa521`) computed across application versions, configuration parameters, and random seeds.

---

## 11. What We Deliberately Did NOT Build

To maintain strict security boundaries and protect payment safety during this buildathon prototype:
- **No Live Payment Execution**: REVIVE does not charge live credit cards, debit cards, or bank accounts.
- **No Real Customer Communications**: No live SMS, WhatsApp Business, or email endpoints are invoked.
- **No Real Razorpay API Keys or Secrets**: The repository operates completely offline without external cloud credentials.
- **Why?** Evaluating autonomous agents on financial recovery requires establishing deterministic proof of recoverability and zero-trust safety boundaries *before* deploying to production payment networks.

---

## 12. Known Limitations

- **Synthetic Calibration**: Decision trees and scoring weights are calibrated on the synthetic lifecycle simulator; real-world merchant distributions may exhibit different failure profiles.
- **Static Latency Model**: Banking gateway response times are simulated statistically rather than sampled from real-time network probes.
- **In-Memory Cache**: Active session states and idempotency caches are hosted in-memory for fast local demonstration.

---

## 13. Buildathon Track Alignment

**Track 3: AI Revenue Recovery (Razorpay AI Buildathon 2026)**
REVIVE directly solves the Track 3 objective by combining AI-driven failure diagnosis, recoverability probability estimation, and net Expected Value optimization with institutional-grade risk governance and immutable auditability.
