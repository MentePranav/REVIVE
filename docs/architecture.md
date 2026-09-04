# REVIVE — System Architecture Specification

## 1. Executive Overview

**REVIVE** is an event-driven autonomous revenue recovery decision system designed for intelligent failed-payment recovery and risk-governed interventions.

Modern digital businesses face significant revenue leakage from failed recurring and one-time payment transactions (card declines, network timeouts, insufficient funds, expired instruments, mandate failures). Traditional payment recovery mechanisms rely on naive indiscriminate retries or static heuristic rules, which lead to high customer friction, payment processor penalties, customer fatigue, and suboptimal recovery yields.

REVIVE solves this by separating **contextual decision intelligence** from **deterministic financial risk policies** to deliver bounded, explainable, and provably incremental revenue recovery.

---

## 2. Core Architecture Principle: Separation of Reasoning & Policy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CONTEXTUAL INTELLIGENCE LAYER                        │
│  • Diagnoses error code & failure context                               │
│  • Evaluates customer history & merchant profile                        │
│  • Formulates candidate recovery strategy & timing                      │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ Candidate Recommendation
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      DETERMINISTIC POLICY GATE                          │
│  • Enforces absolute financial bounds & retry caps                      │
│  • Checks customer fatigue & mandatory cooldown windows                 │
│  • Validates channel constraints & regulatory limits                    │
│  • Outcome: ALLOWED | BLOCKED | ESCALATED                               │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ Validated ExecutionAuthorization
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     CONTROLLED EXECUTION SIMULATOR                      │
│  • Smart scheduled retry                                                │
│  • Dynamic payment link generation                                      │
│  • Alternate payment method nudge (UPI, Netbanking)                     │
│  • Human support escalation                                             │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ Execution Status & Outcome
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     IMMUTABLE AUDIT & OBSERVABILITY                     │
│  • Full reasoning trace, policy verification, timestamps, metrics       │
└─────────────────────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **Decision Boundary Invariant**: The recommendation layer possesses **zero direct execution authority**. All actions recommended by contextual intelligence must pass through the deterministic Policy Engine to receive a validated `ExecutionAuthorization` before any simulated financial action is executed.

---

## 3. End-to-End Data Flow

The lifecycle of every transaction failure event follows an invariant sequence:

```
[ PAYMENT FAILURE EVENT ]
          │
          ▼
   [ 1. DETECT ] ────────► Capture webhook / event payload (error code, metadata)
          │
          ▼
  [ 2. DIAGNOSE ] ───────► Parse root cause (Technical vs Financial vs User-induced)
          │
          ▼
[ 3. SCORE RECOVERABILITY ] ──► Compute P(Recover | Action, Timing, Context)
          │
          ▼
  [ 4. SELECT ACTION ] ──► AI proposes optimal recovery intervention & schedule
          │
          ▼
 [ 5. POLICY GATE ] ────► Deterministic rule evaluation (Veto / Permit / Restrict)
          │
          ├───────────────► If BLOCKED: Log reason, abort or fallback
          ├───────────────► If ESCALATED: Route to merchant human support queue
          └───────────────► If ALLOWED: Dispatch to Action Executor
          │
          ▼
   [ 6. EXECUTE ] ───────► Dispatch action (Scheduled retry / Payment Link / Nudge)
          │
          ▼
[ 7. OBSERVE OUTCOME ] ──► Await status (Success, Decline, Timeout, Expired)
          │
          ▼
   [ 8. AUDIT ] ─────────► Record immutable telemetry in database & metrics log
```

---

## 4. Subsystem Specifications

### 4.1. Ingestion & Webhook Handler (`backend/`)
- **Role**: Receives transaction failure events and status update webhooks from payment gateways (e.g., Razorpay test-mode webhooks) or the transaction simulator.
- **Components**:
  - FastAPI webhook endpoint `/api/v1/webhooks/razorpay` with signature verification.
  - Event normalizer converting disparate gateway payloads into standard `PaymentFailureEvent` schema.

### 4.2. Synthetic Transaction Simulator (`simulator/`)
- **Role**: Generates statistically realistic transaction datasets across merchant verticals (SaaS, E-commerce, EdTech, D2C).
- **Features**:
  - Failure taxonomy (Insufficent funds, Do not honor, Network timeout, Card expired, Authentication failed, Velocity limit).
  - Customer lifecycle & behavioral personas (High-value loyal, churn-risk, price-sensitive, friction-intolerant).
  - Temporal patterns (salary cycles on 1st/30th, weekend banking maintenance, diurnal activity).

### 4.3. Ground-Truth Evaluator & Baselines (`evaluation/`)
- **Role**: Provides unpolluted statistical validation against ground-truth recovery probabilities.
- **Baselines**:
  - **Naive Baseline**: Immediate retry or fixed periodic retries (e.g., +2h, +24h, +48h).
  - **Rule-Based Baseline**: Static heuristic lookup table (e.g., if error 500 retry in 1 hour; if insufficient funds retry on 1st).
- **Benchmark Metrics**:
  - Incremental Recovery Yield ($\Delta \text{Revenue}$).
  - Recovery Efficiency (Recovery Yield / Total Cost of Interventions).
  - Customer Fatigue Index & Cancellation Prevention Rate.

### 4.4. AI Reasoning & Diagnosis Engine (`agent/`)
- **Role**: Multi-factor synthesis of failure telemetry, customer history, merchant economics, and error semantics.
- **Capabilities**:
  - Root cause classification into actionable buckets: `TRANSIENT_SYSTEM`, `CUSTOMER_ACTION_REQUIRED`, `PERMANENT_HARD_DECLINE`, `TIMING_SENSITIVE`.
  - Structured output generation (validated via Pydantic models).
  - Fallback heuristic mode when LLM API is unreachable.

### 4.5. Recovery Scoring Engine (`policy/scoring.py`)
- **Role**: Mathematical formulation of recovery expected value:
  $$\text{EV}(\text{action}) = P(\text{success} \mid \text{action}, t) \times \text{Amount} - \text{Cost}(\text{action}) - \text{Penalty}(\text{churn\_risk})$$
- Computes calibrated recovery probabilities based on historical performance vectors.

### 4.6. Deterministic Policy Engine (`policy/`)
- **Role**: Hard safety gate enforcing invariant business rules:
  - Maximum retry attempts per invoice (e.g., max 3).
  - Cooldown periods between attempts (e.g., minimum 12-24 hours for financial declines).
  - Maximum communication frequency to avoid spamming customers.
  - Maximum allowable discount or incentive for payment links.
  - Mandatory human review escalation for transactions above merchant-defined thresholds.

### 4.7. Bounded Action Executor (`agent/executor.py`)
- **Role**: Safe execution of permitted recovery actions:
  - `SMART_RETRY`: Enqueues an automated payment retry at the optimal predicted timestamp.
  - `PAYMENT_LINK`: Generates an alternate payment link with localized payment options (UPI / Cards / NetBanking).
  - `CUSTOMER_NUDGE`: Sends a friction-free notification (Email/SMS/WhatsApp template).
  - `ESCALATE`: Queues transaction for manual intervention by merchant success team.

### 4.8. Audit System & Data Persistence (`backend/database.py`)
- **Role**: Complete end-to-end traceability of every recovery lifecycle.
- **Storage**: SQLite database with migration capabilities for PostgreSQL.
- **Audit Records**:
  - Exact failure event metadata.
  - Contextual diagnosis, confidence score, and candidate recommendations.
  - Policy evaluation log (rules evaluated, rules passed, rules violated).
  - Executed action and timestamp.
  - Final financial outcome and calculated incremental uplift.

### 4.9. Web Dashboard (`server/static/`)
- **Role**: Intuitive, high-density operator interface for engineering teams, merchants, and evaluators.
- **Key Views**:
  - **Overview / Metrics**: Live recovered revenue, recovery rate vs baselines, active recovery queue.
  - **Decision Stream**: Real-time event log with explainability drawers showing contextual diagnosis vs Policy decisions.
  - **Simulation & Benchmark Lab**: Interactive controls to run synthetic batches, toggle baselines, and inspect lift.
  - **Policy Configuration**: Visual inspection of safety bounds and rule hierarchy.

---

## 5. Security, Risk & Governance Model

1. **Zero Secret Exposure**: All credentials managed strictly via environment variables (`.env`). No secrets committed to version control.
2. **Deterministic Veto**: No candidate recommendation can bypass the Policy Gate. If the Policy Engine rejects an action, the executor cannot run it.
3. **Idempotency**: Every recovery action is assigned an idempotency key to prevent duplicate charges or overlapping retries.
4. **Graceful Degradation**: If diagnosis fails or encounters corrupted context, system fails closed to `HUMAN_REVIEW` or `NO_ACTION_TAKEN`.
