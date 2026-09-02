# REVIVE — Controlled Recovery Execution Simulator

## 1. Executive Summary & Purpose

The **REVIVE Controlled Recovery Execution Simulator** is the deterministic execution layer that converts policy-authorized recovery recommendations into simulated recovery actions, evaluates synthetic outcomes against the simulation environment, and maintains an immutable audit trail.

> [!IMPORTANT]
> **Simulation Disclaimer**: Phase 6 is a local simulation only. It does not perform real-world payment operations, connect to live Razorpay APIs, generate real payment links, or send real SMS/WhatsApp communications. All recovery metrics represent synthetic evaluations under controlled benchmark conditions.

```
┌────────────────────────────────────────────────────────┐
│             SYNTHETIC TRANSACTION / FAILURE            │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│      PHASE 4: DIAGNOSIS & RECOVERY SCORING ENGINE      │
│  • Failure classification & Diagnostic Confidence      │
│  • Recoverability score & Action Expected Value (EV)   │
└───────────────────────────┬────────────────────────────┘
                            │ ReviveRecommendation
                            ▼
┌────────────────────────────────────────────────────────┐
│       PHASE 5: POLICY, SAFETY & GOVERNANCE ENGINE      │
│  • Zero-Trust Hierarchy (P001–P010)                    │
│  • Hard 2-Attempt Cap | 0.85 Confidence Gate | Risk Gate│
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼ (ALLOW ONLY)
┌────────────────────────────────────────────────────────┐
│           IMMUTABLE ExecutionAuthorization             │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│         PHASE 6: CONTROLLED EXECUTION SIMULATOR        │
│  • Validates ExecutionAuthorization Integrity          │
│  • Re-validates Live Payment State (Blocks if CAPTURED)│
│  • Enforces Deterministic Idempotency Key              │
│  • Dispatches Synthetic Recovery Action:               │
│      - RETRY        → Synthetic gateway retry (sim_ret)│
│      - REMINDER     → Approved template (sim_rem)      │
│      - PAYMENT_LINK → Synthetic link token (sim_pl)    │
│      - HUMAN_REVIEW → Escalated to queue (sim_rev)     │
│      - NO_ACTION    → Passive observation              │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│          PHASE 2 SYNTHETIC OUTCOME SIMULATION          │
│  • Evaluates outcome strictly AFTER action execution   │
│  • Zero ground-truth leakage into decision path        │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│            IMMUTABLE AUDIT TRAIL & TRACE LOG           │
└────────────────────────────────────────────────────────┘
```

---

## 2. Strict Execution Boundary

The `ControlledExecutor` structurally refuses to act on raw recommendations. It strictly requires a valid `ExecutionAuthorization` issued by the `PolicyEngine`:

- **Missing Authorization**: Blocked (`EXECUTION_BLOCKED_MISSING_AUTHORIZATION`).
- **Unauthorized Status**: Blocked (`EXECUTION_BLOCKED_UNAUTHORIZED`).
- **Customer / Payment Mismatch**: Blocked (`EXECUTION_BLOCKED_CUSTOMER_MISMATCH`).
- **Unsupported Action**: Blocked (`EXECUTION_BLOCKED_UNSUPPORTED_ACTION`).
- **Policy Version Mismatch**: Rejected.

---

## 3. Supported Actions & Synthetic Execution Mechanics

| Action | Execution Status | Simulated Mechanism | External Reference Format |
|---|---|---|---|
| **`NO_ACTION`** | `NO_ACTION_TAKEN` | Passive observation; no state change. | `None` |
| **`RETRY`** | `EXECUTED` | Simulated backend retry with processor. | `sim_ret_<hash10>` |
| **`REMINDER`** | `EXECUTED` | Dispatches approved template (`REMINDER_STANDARD_V1`). | `sim_rem_<hash10>` |
| **`PAYMENT_LINK`** | `EXECUTED` | Generates synthetic payment link (`PAYMENT_LINK_STANDARD_V1`). | `sim_pl_<hash10>` |
| **`HUMAN_REVIEW`** | `HUMAN_REVIEW_REQUIRED` | Enqueues opportunity for manual agent review. | `sim_rev_<hash10>` |

---

## 4. Idempotency & Duplicate Prevention

To prevent duplicate interventions and double-charging, the executor calculates a deterministic idempotency key:

$$\text{ExecutionKey} = \text{SHA256}(\text{payment\_id} : \text{authorization\_id} : \text{action})[0:16]$$

Repeated execution calls with the same key immediately return the cached original result without re-executing actions or double-counting recovered revenue (`AuditEventType.DUPLICATE`).

---

## 5. Live State Re-Validation (Race Condition Guard)

Even with a valid `ExecutionAuthorization`, the executor performs a just-in-time check on the live `PaymentStateContext` immediately prior to simulated dispatch:
- If `current_status == SUCCESS` or `is_already_resolved == True`: Execution is blocked with `EXECUTION_BLOCKED_PAYMENT_STATE_CHANGED`.
- This enforces the core principle: **Authorization $\neq$ Permanent Permission**.

---

## 6. End-to-End Lifecycle Trace Example

A single transaction can be audited from failure to resolution using the CLI:

```powershell
python -m execution.cli --dataset data/ --trace-event txn_00002929
```

```text
================================================================================
               REVIVE LIFECYCLE TRACE: txn_00002929               
================================================================================
Event ID              : txn_00002929
Customer ID           : cust_000438
Amount                : INR 1,109.18
Diagnosis             : AUTHENTICATION (Confidence: 92.0%)
Recoverability Score  : 80.7% (HIGH)
Recommended Action    : REMINDER
--------------------------------------------------------------------------------
Policy Decision       : ALLOW (Rule: P010_ACTION_APPROVED)
Policy Reason         : Recovery action 'REMINDER' approved by policy governance engine.
Authorization ID      : auth_59b23c2294c3 (Version: 1.0.0)
--------------------------------------------------------------------------------
Execution Status      : EXECUTED
Execution Reason      : Simulated reminder dispatched using template 'REMINDER_STANDARD_V1'.
External Reference    : sim_rem_96d6de7a4c
Recovery Outcome      : RECOVERED
Recovered Amount      : INR 1,109.18
--------------------------------------------------------------------------------
AUDIT TRAIL:
  [2026-01-01T00:37:35Z] REQUESTED                 - {"has_authorization": true}
  [2026-01-01T00:37:35Z] AUTHORIZATION_VALIDATED   - {"authorization_id": "auth_59b23c2294c3", "policy_version": "1.0.0"}
  [2026-01-01T00:37:35Z] EXECUTED                  - {"execution_status": "EXECUTED", "external_reference": "sim_rem_96d6de7a4c"}
  [2026-01-01T00:37:35Z] OUTCOME_RECORDED          - {"recovery_outcome": "RECOVERED", "recovered_amount": 1109.18}
================================================================================
```

---

## 7. Batch Execution Report (10,000 Transaction Benchmark)

```text
================================================================================
         REVIVE CONTROLLED RECOVERY EXECUTION SIMULATOR REPORT          
================================================================================
Total Transactions Evaluated   : 10,000
Failure Opportunities Analyzed : 2,226
Execution Latency              : 486.03 ms (4,579.9 opps/sec)
--------------------------------------------------------------------------------
POLICY & EXECUTION GATING:
  Policy Authorized (ALLOW)    : 1,324 (59.5%)
  Human Review Escalations     : 676 (30.4%)
  Passive / No Action          : 71 (3.2%)
  Policy Denied                : 155
  Actions Successfully Executed: 1,324
  Actions Blocked at Executor  : 155
--------------------------------------------------------------------------------
FINANCIAL RECOVERY PERFORMANCE (INR):
  Revenue at Risk              : INR 7,271,642.30
  Natural Recovery (NO_ACTION) : INR    47,999.51
  REVIVE Total Recovered       : INR 2,478,691.50
  Incremental Revenue Uplift   : INR 2,430,691.99
  Intervention Success Rate    :        55.6%
  Overall Opportunity Capture  :        33.1%
--------------------------------------------------------------------------------
ACTION-LEVEL BREAKDOWN:
Action          | Recommended  | Authorized  | Executed  | Recovered (INR)  | Success Rate
--------------------------------------------------------------------------------
RETRY           |          416 |         193 |       193 | INR   322,932.71 |        97.9%
PAYMENT_LINK    |          714 |         286 |       286 | INR   178,278.44 |        47.2%
REMINDER        |          991 |         845 |       845 | INR 1,977,480.35 |        48.8%
DO_NOTHING      |           90 |           0 |         0 | INR         0.00 |         0.0%
HUMAN_REVIEW    |           15 |           0 |         0 | INR         0.00 |         0.0%
================================================================================
```
