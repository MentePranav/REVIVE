# REVIVE — Synthetic Payment & Customer Lifecycle Simulator

## 1. Overview & Purpose

The **REVIVE Synthetic Payment Simulator** provides a statistically controlled, reproducible data environment for evaluating autonomous revenue recovery mechanisms.

In real-world payment ecosystems, payment failures are not independent random events. They are deeply correlated with:
- **Customer Lifecycle & History** (loyal subscription vs new one-off buyer vs chronically delinquent user)
- **Failure Taxonomy** (transient gateway timeout vs bank-side decline vs expired card vs insufficient balance)
- **Temporal Patterns** (salary cycles, day-of-month effects, diurnal windows)
- **Economic Value & Channel Friction** (micro-transactions vs high-value enterprise invoices)

The simulator generates synthetic merchant payment data paired with a **hidden causal ground-truth layer** that allows benchmarking REVIVE against naive retries, heuristic baselines, and human workflows without data leakage.

> [!NOTE]
> **Scope & Positioning**: This is a controlled synthetic payment environment designed to reproduce realistic payment lifecycle patterns and enable objective evaluation. It models representative Indian payment ecosystems (UPI, Cards, NetBanking, Wallets) and Razorpay-like diagnostic semantics.

---

## 2. Customer Behavioral Profiles

The population generator models 6 distinct behavioral customer profiles:

| Profile | Population Share | Historical Success Rate | Transaction Volume | Mean Amount Range | Preferred Methods | Primary Failure Types |
|---|---|---|---|---|---|---|
| **`PROFILE_A_RELIABLE`** | 35% | 90% – 99% | High (8–50 txns) | ₹399 – ₹3,500 | UPI, Card | Transient timeouts, OTP typos |
| **`PROFILE_B_OCCASIONAL_FAILURE`** | 25% | 70% – 85% | Moderate (5–30 txns) | ₹299 – ₹2,499 | UPI, Card, Wallet | Bank decline, transient timeouts |
| **`PROFILE_C_HIGH_FAILURE`** | 10% | 25% – 50% | Moderate (3–20 txns) | ₹199 – ₹1,999 | UPI, Card, Wallet | Insufficient funds, repeated declines |
| **`PROFILE_D_NEW_CUSTOMER`** | 10% | Variable (0–2 txns) | Low (0–2 txns) | ₹199 – ₹1,499 | UPI | User cancellation, OTP abandonment |
| **`PROFILE_E_SUBSCRIPTION`** | 12% | 80% – 95% | Periodic (30-day interval) | ₹299 – ₹4,999 | Card, UPI AutoPay | Expired cards, mandate limits |
| **`PROFILE_F_HIGH_VALUE`** | 8% | 85% – 97% | Low to Moderate (5–40) | ₹12,000 – ₹1,25,000 | Corporate NetBanking, Card | Bank auth limits, velocity flags |

---

## 3. Transaction & Funnel Generation

### 3.1. Temporal Monotonicity
For every customer, transactions are chronologically ordered ($T_1 < T_2 < \dots < T_n$). Subscription customers exhibit periodic intervals ($\approx 30$ days $\pm 2$ hours), while retail consumers exhibit Poisson/Gamma-distributed inter-arrival times.

### 3.2. Status & Amount Distributions
- **Target Distribution**: ~80% `SUCCESS`, ~13% `FAILED`, ~7% `ABANDONED` checkouts.
- **Amounts**: Sampled from calibrated lognormal mixture distributions spanning micro-transactions (₹49), everyday retail (₹500–₹2,500), and high-value enterprise tiers (up to ₹2,50,000).
- **Payment Methods**: 45–55% `UPI` (Intent / Collect), 25% `CARD` (Debit / Credit), 12–15% `NETBANKING` (Retail / Corporate), 8–15% `WALLET`.

---

## 4. Failure Taxonomy & Razorpay-like Diagnostic Semantics

Failed payments include correlated diagnostic attributes matching gateway webhook specifications:

```json
{
  "error_source": "gateway",
  "error_step": "payment_processing",
  "error_reason": "timeout",
  "error_code": "GATEWAY_ERROR_TIMEOUT",
  "error_description": "The payment gateway timed out while communicating with the processor.",
  "failure_category": "TRANSIENT_GATEWAY_FAILURE"
}
```

### Supported Categories
1. **`TRANSIENT_GATEWAY_FAILURE`**: Gateway / network timeouts during processing. Highly recoverable via smart retries.
2. **`BANK_DECLINE`**: Issuer authorization rejection. Recoverable via alternate card/netbanking links or limit adjustments.
3. **`INSUFFICIENT_FUNDS`**: Temporary shortage. Retrying immediately fails; payment links timed around salary dates or reminders recover effectively.
4. **`AUTHENTICATION_FAILURE`**: OTP typo or 3DS timeout. Recoverable via lightweight friction-free reminder.
5. **`PAYMENT_METHOD_FAILURE`**: Expired card or inactive UPI ID. Requires updating payment instrument via payment link.
6. **`USER_ABANDONMENT`**: Drop-off during checkout or gateway redirect.
7. **`HARD_FAILURE`**: Permanently blocked or restricted account. Automated recovery is prohibited.
8. **`HIGH_RISK`**: Flagged by fraud / velocity checks. Requires human compliance review.

---

## 5. Evaluation-Only Ground Truth Architecture

To prevent data leakage during agent evaluation, datasets are strictly partitioned into **Public/Model-Visible Models** and **Evaluation-Only Ground Truth**:

```
┌────────────────────────────────────────────────────────┐
│               PUBLIC DATA (Inference Visible)          │
│  • Customer Profile & History (aggregate counts)       │
│  • Transaction Metadata (Amount, Method, Timestamp)    │
│  • Diagnostic Failure Details (Error Code, Reason)     │
│  • Abandoned Checkout Telemetry (Stage, Time Spent)    │
└────────────────────────────────────────────────────────┘
                            │
              (Strict Isolation Boundary)
                            ▼
┌────────────────────────────────────────────────────────┐
│             HIDDEN GROUND TRUTH (Evaluation Only)      │
│  • ground_truth_recoverable (bool)                     │
│  • ground_truth_best_action (RETRY, PAYMENT_LINK, ...) │
│  • ground_truth_recovery_probability (float [0, 1])    │
│  • ground_truth_customer_friction (float [0, 1])       │
│  • counterfactual_outcomes (Map: Action -> Outcome)    │
│  • is_already_resolved (bool: Organic Late Capture)    │
└────────────────────────────────────────────────────────┘
```

### Counterfactual Outcome Matrix
For every eligible failure event, the simulator pre-calculates the deterministic outcome of applying any candidate intervention:
- **`RETRY`**
- **`PAYMENT_LINK`**
- **`REMINDER`**
- **`DO_NOTHING`**
- **`HUMAN_REVIEW`**

Possible simulated resolutions: `SUCCESS`, `FAILURE`, `NO_RESPONSE`, `ALREADY_RESOLVED`.

---

## 6. CLI Usage & Reproducibility

The simulator is fully deterministic given a random seed.

### Command-Line Interface
```bash
# Generate default 10,000 transaction dataset with seed 42
python -m simulator.generate --transactions 10000 --seed 42 --output data/

# Generate custom 50,000 transaction benchmark
python -m simulator.generate --transactions 50000 --customers 8000 --seed 123 --output data/
```

### Output Files (`data/`)
- `customers.jsonl`: Synthetic customer records with historical performance vectors.
- `transactions.jsonl`: Public transaction records with failure diagnostics.
- `abandoned_checkouts.jsonl`: Funnel abandonment telemetry.
- `ground_truth.jsonl`: Evaluation-only causal benchmark records.
- `dataset_summary.json`: JSON metadata containing calculated distributions.

---

## 7. Data Validation & Quality Invariants

The `DatasetValidator` enforces 10 automated checks prior to persisting datasets:
1. **Uniqueness**: Zero duplicate transaction, payment, or checkout IDs.
2. **Referential Integrity**: 100% of transactions and checkouts reference valid customers.
3. **Chronological Validity**: Customer timelines are strictly monotonic ($T_i \le T_{i+1}$).
4. **Financial Validity**: 100% of transaction and checkout amounts are strictly positive ($> 0$).
5. **Semantic Integrity**: Error codes, steps, sources, and reasons match failure categories.
6. **Zero Leakage**: Public models contain zero `ground_truth_` or `counterfactual_` fields.
7. **Customer History Sanity**: $\text{Total} = \text{Success} + \text{Failure}$, $\text{Rate} = \frac{\text{Success}}{\text{Total}}$.
8. **Funnel Sanity**: Abandoned checkouts possess valid stages and non-negative time-on-page.
