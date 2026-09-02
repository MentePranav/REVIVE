# REVIVE — Safety, Governance & Zero-Trust Execution Framework

*Note: All governance rules, attempt limits, and safety gates described in this document reflect the internal architecture of the REVIVE evaluation and simulation engine.*

---

## 1. Zero-Trust Execution Architecture

In REVIVE, **a model recommendation is never permission to execute**.

Traditional recovery systems couple optimization directly with execution, meaning an AI model predicting high probability can directly trigger a charge. REVIVE breaks this vulnerability by enforcing a strict physical separation between intelligence and execution:

```text
┌─────────────────────────┐
│   REVIVE INTELLIGENCE   │  --> Produces: Contextual Recommendation (Unverified)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  POLICY & SAFETY ENGINE │  --> Evaluates: Deterministic Safety Gates (P001 - P009)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ EXECUTION AUTHORIZATION │  --> Issues: Cryptographic Token (P010) strictly if ALLOW
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   CONTROLLED EXECUTOR   │  --> Re-validates Token & State before Action Simulation
└─────────────────────────┘
```

---

## 2. Comprehensive Policy Gate Hierarchy ($P001$–$P010$)

Before any action is authorized, it must pass an unbroken chain of deterministic rules:

### $P001$ — Input & Schema Integrity
- Validates that transaction amount is strictly positive ($> 0$), currency is recognized (`INR`), and required identifiers (`payment_id`, `customer_id`) exist.
- **Fail-Closed**: Any schema irregularity or negative value is rejected immediately.

### $P002$ — Anti-Double-Recovery & Payment State Check
- Verifies the live payment status before execution.
- If a payment is already `CAPTURED`, `SUCCESS`, or marked `is_already_resolved = True`, execution is strictly blocked (`DENY`). This prevents attempts on transactions settled out-of-band.

### $P003$ — Automated Stopping Rules (2-Attempt Hard Cap)
- Prohibits infinite retry loops on failing payments.
- Enforces a hard ceiling of **at most 2 automated recovery attempts per payment ID**. If attempt count $\ge 2$, automated recovery is refused.

### $P004$ — Diagnostic Confidence Gate
- Evaluates the model's diagnostic certainty.
- If root-cause confidence is below **85% ($< 0.85$)**, the system halts automation and routes the event to the **Human Review Queue** (624 cases / 5.64% of failed opportunities in benchmark).

### $P005$ — High-Risk Fraud & Risk Gate
- Enforces zero automated interventions on accounts flagged with fraud, suspicious IP velocity, or high chargeback history.
- Flagged cases are blocked from automated retries and escalated immediately to Human Review.

### $P006$ — Action Allowlist Check
- Enforces that only enumerated, permitted actions (`RETRY`, `REMINDER`, `PAYMENT_LINK`, `DO_NOTHING`) can be authorized. Injected strings (e.g. `"REFUND"`) fail closed cleanly.

### $P007$ — Customer Contact Fatigue Limits
- Protects customers from notification spam.
- Limits reminders and payment links to a maximum of **2 communications per customer**.

### $P008$ — Mandatory Cooldown Interval
- Enforces a minimum **300-second (5-minute) pause** between successive recovery attempts on the same transaction to allow bank queues to settle.

### $P009$ — Template Whitelist Check
- Communication templates must match pre-registered merchant templates (`REMINDER_STANDARD_V1`, `PAYMENT_LINK_STANDARD_V1`).

### $P010$ — Cryptographic Authorization Token Issuance
- An `ExecutionAuthorization` token containing an authorization ID, policy version, and timestamp is generated **only** when all safety rules evaluate to `ALLOW`.

---

## 3. Idempotency & Concurrency Safeguards

To prevent duplicate execution caused by network retries, browser double-clicks, or race conditions:
1. The executor computes a deterministic SHA-256 idempotency key:
   $$\text{Key} = \text{SHA-256}(\text{payment\_id} : \text{authorization\_id} : \text{action})$$
2. Prior to executing, the key is checked against the session `execution_cache`.
3. If an execution key is already present, the executor returns the cached outcome with a `DUPLICATE` audit event without triggering a secondary simulation.

---

## 4. Fail-Closed Behavioral Safeguards

Under every anomalous or edge condition, REVIVE defaults to **Fail-Closed**:
- **Malformed Input**: Blocked ($P001$).
- **Stale Authorization Token ($> 24\text{h}$)**: Rejected by executor.
- **Mismatched Token & Payment ID**: Rejected by executor.
- **Unapproved Action or Template**: Denied ($P006$ / $P009$).
- **Internal Exception**: Trapped and logged without dispatching actions.

---

## 5. Explicit Boundary: Simulation vs. Production

| Proven in Simulation & Regression Suite | Requires Production Validation & Setup |
| :--- | :--- |
| **Proven**: Strict zero-trust separation between intelligence and executor. | **Requires**: Integration with live Razorpay webhooks (`payment.failed`, `order.paid`). |
| **Proven**: Hard 2-attempt stopping cap ($P003$) and 300s cooldown enforcement. | **Requires**: Distributed idempotency store (e.g. Redis/PostgreSQL) across server replicas. |
| **Proven**: 100% high-risk fraud cases routed to Human Review in synthetic data. | **Requires**: Live risk scoring telemetry and KYC/AML compliance feeds. |
| **Proven**: 69 adversarial edge cases tested with 0 unauthorized executions. | **Requires**: Canary A/B testing on live merchant traffic with safety circuit breakers. |
