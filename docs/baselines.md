# REVIVE — Baseline Recovery Strategies & Benchmark Engine

## 1. Executive Summary & Purpose

The **REVIVE Baseline Evaluation Engine** establishes rigorous, transparent, and reproducible benchmarks for revenue recovery performance prior to the introduction of AI-driven agents.

In commercial payment recovery, evaluating an autonomous agent without credible baselines creates the risk of claiming artificial lift over an unoptimized strawman. To ensure scientific rigor, REVIVE compares performance against:
1. **`NO_ACTION`**: Passive baseline establishing natural organic recovery.
2. **`NAIVE_RETRY`**: Simplistic global single-retry strategy commonly seen in naive implementations.
3. **`RULE_BASED`**: Sophisticated, deterministic heuristic engine mapping observable gateway telemetry, customer context, and amount tiers to bounded recovery actions.

> [!NOTE]
> **Scope & Benchmark Context**: These are controlled synthetic benchmarks designed to evaluate algorithm performance under identical simulation conditions. They do not constitute claims about Razorpay’s production gateway recovery rates.

---

## 2. Standardized Action Vocabulary

All strategies and evaluators adhere to a unified, controlled action space:

| Action | Execution Semantics | Typical Use Case | Synthetic Unit Cost (INR) |
|---|---|---|---|
| **`DO_NOTHING` / `NO_ACTION`** | Passive observation; no intervention dispatched. | Permanent declines, early abandonments. | ₹0.00 |
| **`RETRY`** | Automated backend payment retry with gateway. | Transient gateway timeouts, network blips. | ₹2.00 |
| **`REMINDER`** | Low-friction customer notification (SMS/WhatsApp). | Authentication/OTP typos, checkout drop-off. | ₹1.50 |
| **`PAYMENT_LINK`** | Dynamic payment link with alternate payment methods. | Insufficient balance, expired cards/mandates. | ₹3.00 |
| **`HUMAN_REVIEW`** | Escalation to high-touch merchant support/fraud queue. | High-value declines (>₹50k), velocity risk flags. | ₹50.00 |

---

## 3. Implemented Baseline Strategies

### 3.1. Baseline A — `NO_ACTION`
- **Philosophy**: Completely passive observation.
- **Behavior**: Emits `RecoveryAction.DO_NOTHING` (`rule_id: R000_NO_ACTION`) for all events.
- **Purpose**: Establishes the organic recovery rate ($R_{\text{natural}}$) resulting from late payment capture settlements where customers resolve issues independently.

### 3.2. Baseline B — `NAIVE_RETRY`
- **Philosophy**: Indiscriminate single automated retry.
- **Behavior**:
  - For eligible failed transactions: Emits `RecoveryAction.RETRY` (`rule_id: R_NAIVE_GLOBAL_RETRY`).
  - Strict constraints: Enforces a single retry budget per payment. Skips terminal `HARD_FAILURE` errors and abandoned checkouts.
- **Limitation**: Suffers from low precision because retrying insufficient balance or expired cards repeatedly fails.

### 3.3. Baseline C — `RULE_BASED`
- **Philosophy**: Industry best-practice heuristic expert system.
- **Behavior**: Inspects observable gateway telemetry and customer attributes:

| Rule ID | Trigger Condition | Assigned Action | Domain Rationale |
|---|---|---|---|
| **`R001_TRANSIENT_RETRY`** | `TRANSIENT_GATEWAY_FAILURE` | `RETRY` | Network/processor timeouts resolve with immediate/short-delay retry. |
| **`R002_INSUFFICIENT_FUNDS_PAYMENT_LINK`** | `INSUFFICIENT_FUNDS` | `PAYMENT_LINK` | Immediate retry fails; payment link allows customer to use alternate card/account. |
| **`R003_AUTH_FAILURE_REMINDER`** | `AUTHENTICATION_FAILURE` | `REMINDER` | Dropped 3DS/OTP sessions recover effectively with a friction-free push reminder. |
| **`R004_METHOD_FAILURE_PAYMENT_LINK`** | `PAYMENT_METHOD_FAILURE` | `PAYMENT_LINK` | Expired card or inactive VPA requires customer to input a fresh instrument. |
| **`R005A_HIGH_VALUE_BANK_DECLINE_ESCALATE`** | `BANK_DECLINE` & Amount $\ge ₹50,000$ | `HUMAN_REVIEW` | High-value VIP/enterprise invoices warrant manual triage. |
| **`R005B_BANK_DECLINE_PAYMENT_LINK`** | `BANK_DECLINE` & Amount $< ₹50,000$ | `PAYMENT_LINK` | Standard bank decline prompts customer to switch payment method. |
| **`R006_ABANDONED_CHECKOUT_REMINDER`** | Abandonment at `OTP_STAGE` / `PAYMENT_SUBMISSION` | `REMINDER` | Recovers high-intent funnel drop-offs. |
| **`R006B_EARLY_ABANDONMENT_SKIP`** | Abandonment at `CHECKOUT_STARTED` | `DO_NOTHING` | Avoids spamming casual window shoppers. |
| **`R007_HARD_FAILURE_STOP`** | `HARD_FAILURE` (Blocked/stolen card) | `DO_NOTHING` | Prevents futile automated retries on permanently blocked accounts. |
| **`R008A_HIGH_RISK_MANUAL_REVIEW`** | `HIGH_RISK` & Amount $\ge ₹20,000$ | `HUMAN_REVIEW` | Fraud/velocity flag escalated to risk operations team. |
| **`R008B_HIGH_RISK_BLOCK`** | `HIGH_RISK` & Amount $< ₹20,000$ | `DO_NOTHING` | Automatic block on anomalous micro-transactions. |

---

## 4. Evaluation Methodology & Fairness Guarantees

```
┌────────────────────────────────────────────────────────┐
│             PUBLIC DATASET (.jsonl stream)             │
│  (Transactions, Abandoned Checkouts, Customer History) │
└───────────────────────────┬────────────────────────────┘
                            │ (Public Models Only)
                            ▼
┌────────────────────────────────────────────────────────┐
│                   RECOVERY STRATEGY                    │
│    (NO_ACTION | NAIVE_RETRY | RULE_BASED | REVIVE)     │
└───────────────────────────┬────────────────────────────┘
                            │ StrategyDecision
                            ▼
┌────────────────────────────────────────────────────────┐
│                   LIFECYCLE GUARDS                     │
│  • Enforces non-duplication & max attempt caps         │
│  • Prevents actions on SUCCESS / terminal states       │
└───────────────────────────┬────────────────────────────┘
                            │ Approved Decision
                            ▼
┌────────────────────────────────────────────────────────┐
│             OUTCOME EVALUATOR (Zero-Leakage)           │
│  • Matches decision against hidden GroundTruthRecord   │
│  • Simulates outcome: SUCCESS | FAILURE | RESOLVED     │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                METRICS & BENCHMARK REPORT              │
└────────────────────────────────────────────────────────┘
```

### Core Invariants
1. **Zero Ground-Truth Leakage**: Strategies are passed strictly public Pydantic models. Evaluation-only fields (`ground_truth_recoverable`, `counterfactual_outcomes`) are isolated in the `OutcomeEvaluator`.
2. **No Look-Ahead**: Events are delivered in strict chronological order ($T_i \le T_{i+1}$). At time $T_i$, subsequent transactions or late capture events are strictly invisible.
3. **Identical Simulation Environment**: All strategies face the exact same counterfactual outcome matrices on identical datasets.

---

## 5. Mathematical Metric Definitions

1. **Natural Recovery Revenue ($R_{\text{natural}}$)**:
   $$R_{\text{natural}} = \sum_{e \in \text{Events}} \text{Amount}(e) \cdot \mathbb{I}(\text{Organically Resolved})$$

2. **Total Recovered Revenue ($R_{\text{strategy}}$)**:
   $$R_{\text{strategy}} = \sum_{e \in \text{Events}} \text{RecoveredAmount}(e, \text{Action})$$

3. **Incremental Revenue Uplift ($\Delta R$)**:
   $$\Delta R = \max(0, R_{\text{strategy}} - R_{\text{natural}})$$

4. **Intervention Precision**:
   $$\text{Precision} = \frac{|\{e \mid \text{Action}(e) \neq \text{DO\_NOTHING} \land \text{Outcome}(e) = \text{SUCCESS}\}|}{|\{e \mid \text{Action}(e) \neq \text{DO\_NOTHING}\}|}$$

5. **Recoverable Opportunity Capture Rate (Evaluation-Only)**:
   $$\text{Capture Rate} = \frac{|\{e \mid \text{IsRecovered}(e) = \text{True}\}|}{|\{e \mid \text{GroundTruthRecoverable}(e) = \text{True}\}|}$$

6. **Net Incremental Economic Value**:
   $$\text{Net Value} = \Delta R - \sum_{e \in \text{Events}} \text{ActionCost}(\text{Action}(e))$$

---

## 6. Benchmark Results (10,000 Transaction Benchmark)

Generated on default seed `42` across 1,426 failed transactions and 800 abandoned checkouts:

| Strategy | Total Recovered | Incremental Uplift | Interventions Attempted | Successful Recoveries | Precision | Capture Rate | Net Economic Value |
|---|---|---|---|---|---|---|---|
| **`NO_ACTION`** | ₹47,999.51 | ₹0.00 | 0 | 0 | 0.0% | 2.2% | ₹0.00 |
| **`NAIVE_RETRY`** | ₹826,112.48 | ₹778,112.97 | 1,353 | 411 | 30.4% | 31.6% | ₹775,406.97 |
| **`RULE_BASED`** | ₹3,308,688.94 | ₹3,260,689.43 | 1,681 | 1,206 | 71.7% | 92.8% | ₹3,253,300.93 |

---

## 7. CLI Usage

```powershell
# Evaluate a single strategy
python -m evaluation.run --strategy rule_based --dataset data/ --output data/evaluations/

# Run comparative benchmark across all baselines
python -m evaluation.compare --dataset data/ --output data/evaluations/
```
