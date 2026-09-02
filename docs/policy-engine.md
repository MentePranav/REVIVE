# REVIVE — Policy, Safety & Governance Engine

## 1. Executive Summary & Core Security Principle

The **REVIVE Policy, Safety & Governance Engine** serves as the authoritative gatekeeper between predictive intelligence and automated financial action:

> **Optimization may recommend. Policy may authorize. Execution may act.**

In autonomous revenue recovery, relying solely on an optimization model to govern execution introduces critical operational risks (e.g. infinite retry loops, double-charging already-resolved customers, customer messaging fatigue, and policy violation). REVIVE implements a **Zero-Trust Governance Layer** where no recommendation is executed without explicit, multi-stage policy authorization.

```
┌────────────────────────────────────────────────────────┐
│             REVIVE SCORING & RECOMMENDATION            │
│         "What action maximizes expected value?"        │
└───────────────────────────┬────────────────────────────┘
                            │ ReviveRecommendation
                            ▼
┌────────────────────────────────────────────────────────┐
│              ZERO-TRUST POLICY ENGINE                  │
│       "Is REVIVE permitted to take that action?"       │
│                                                        │
│  1. Input Validity (P001)                              │
│  2. Payment State Verification (P002)                  │
│  3. Hard 2-Attempt Stopping Rule (P003)                │
│  4. Action Allowlist Verification (P006)               │
│  5. High-Risk Security Gate (P005)                     │
│  6. Diagnosis Confidence Gate ≥ 0.85 (P004)            │
│  7. Customer Contact Limits (P007)                     │
│  8. 5-Minute Action Cooldown (P008)                    │
│  9. Approved Communication Template Check (P009)       │
│ 10. Policy Authorization (P010)                        │
└───────────────┬────────────────────────┬───────────────┘
                │                        │
       [ ALLOW ]                         [ DENY / HUMAN_REVIEW / NO_ACTION ]
                │                                │
                ▼                                ▼
┌────────────────────────────────┐ ┌────────────────────────────────┐
│     ExecutionAuthorization     │ │    No Execution Token Issued   │
│  (Cryptographic-style Token)   │ │  (Execution Structurally Blocked)│
└───────────────┬────────────────┘ └─────────────┬──────────────────┘
                │                                │
                ▼                                ▼
┌───────────────────────────────────────────────────────────────────┐
│                     IMMUTABLE AUDIT LOG RECORD                    │
│  (Machine-readable trace with policy version & evaluation checks)  │
└───────────────────────────────────────────────────────────────────┘
```

> [!NOTE]
> **Scope & Simulation Context**: These safety rules and cooldown periods are controlled benchmark policies designed for reproducible evaluation. They do not constitute claims about Razorpay’s production gateway policies.

---

## 2. Policy Rule Taxonomy ($P001 - P010$)

| Rule ID | Policy Check | Trigger Condition | Assigned Decision |
|---|---|---|---|
| **`P001_INVALID_INPUT`** | Metadata Integrity | Missing `event_id`, `customer_id`, or `amount` $\le 0$ | `DENY` |
| **`P002_PAYMENT_ALREADY_RESOLVED`** | Settlement State | Payment is `SUCCESS`, `CAPTURED`, `REFUNDED`, or `ALREADY_RESOLVED` | `DENY` |
| **`P003_MAX_AUTOMATED_ATTEMPTS`** | Hard Attempt Cap | Payment reached $\ge 2$ automated attempts or $\ge 2$ retries | `DENY` |
| **`P004_LOW_DIAGNOSIS_CONFIDENCE`** | Confidence Gate | Diagnosis confidence $< 0.85$ on active action | `HUMAN_REVIEW` |
| **`P005_HIGH_RISK_GATE`** | Risk / Fraud Gate | Gateway risk telemetry flags `RiskSignal.HIGH` | `HUMAN_REVIEW` |
| **`P006_ACTION_NOT_ALLOWLISTED`** | Allowlist Safety | Action is not in `{DO_NOTHING, RETRY, REMINDER, PAYMENT_LINK, HUMAN_REVIEW}` | `DENY` |
| **`P007_CUSTOMER_CONTACT_LIMIT`** | Customer Fatigue | Customer received $\ge 2$ communication interventions | `DENY` |
| **`P008_COOLDOWN_ACTIVE`** | Rate Limiting | Time elapsed since last action $< 300$ seconds (5 minutes) | `DENY` |
| **`P009_UNAPPROVED_TEMPLATE`** | Template Safety | Communication action references unapproved template ID | `DENY` |
| **`P010_ACTION_APPROVED`** | Authorization | All safety rules pass | `ALLOW` / `NO_ACTION` |

---

## 3. Core Hard Constraints

### 3.1. Absolute Stopping Rule ($P003$)
- **Invariant**: REVIVE must never perform more than **two automated recovery attempts** for the same `payment_id`.
- **Enforcement**: Hard-coded state check in `PolicyEngine`. Cannot be overridden by high recoverability scores or financial yield.

### 3.2. Payment State Invariant ($P002$)
- **Invariant**: Never intervene on captured, successful, or settled payments.
- **Enforcement**: Prevents revenue double-counting and duplicate charges.

### 3.3. Confidence Gate ($P004$)
- **Invariant**: Minimum diagnosis confidence threshold of **0.85** for autonomous action.
- **Enforcement**: If $\text{Confidence} < 0.85$, the case is routed to `HUMAN_REVIEW` for manual merchant triage.

### 3.4. Communication Template Registry ($P009$)
- **Invariant**: Model recommendations cannot generate or inject arbitrary message strings.
- **Approved Templates**:
  - `REMINDER_STANDARD_V1`: Frictionless OTP/drop-off payment reminder.
  - `PAYMENT_LINK_STANDARD_V1`: Alternate payment method link.
  - `CHECKOUT_RECOVERY_V1`: Abandoned cart recovery link.

---

## 4. Execution Authorization Design

To enforce architectural boundaries between governance and execution:
- An `ExecutionAuthorization` object is instantiated **strictly when the decision is `ALLOW`**.
- For `DENY`, `HUMAN_REVIEW`, or `NO_ACTION`, `execution_authorization = None`.
- Downstream executors verify the presence of `ExecutionAuthorization` before making API calls.

```json
{
  "authorization_id": "auth_9f83ac124b89",
  "authorized": true,
  "payment_id": "pay_00000018",
  "action": "RETRY",
  "template_id": null,
  "policy_version": "1.0.0",
  "authorized_at": "2026-01-15T12:00:00Z"
}
```

---

## 5. Batch Governance Report (Benchmark Dataset)

Evaluated across 2,226 recommendations from Phase 4:

```text
======================================================================
            REVIVE POLICY, SAFETY & GOVERNANCE REPORT           
======================================================================
Recommendations Evaluated     : 2,226
Policy Engine Version         : 1.0.0
Execution Latency             : 111.16 ms (20,024.7 decisions/sec)
----------------------------------------------------------------------
POLICY DECISION BREAKDOWN:
  ALLOW (Authorized)          :  66.0%  (1,470)
  HUMAN_REVIEW (Escalated)    :  30.7%  (683)
  NO_ACTION (Passive)         :   3.3%  (73)
  DENY (Blocked)              :   0.0%  (0)
----------------------------------------------------------------------
SAFETY & POLICY GATING BREAKDOWN:
  Confidence Gate (< 0.85)    : 651
  High-Risk Gate Flagged      : 19
  Attempt Cap Exceeded        : 0
  Payment Already Resolved    : 0
  Customer Contact Limit      : 0
  Cooldown Active             : 0
======================================================================
```
