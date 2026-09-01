# REVIVE — Diagnosis & Recovery Scoring Engine

## 1. Executive Summary & Architecture

The **REVIVE Diagnosis & Recovery Scoring Engine** is the contextual intelligence layer for autonomous revenue recovery.

Rather than relying on brittle, static if-else rules or ungrounded black-box calls, REVIVE processes public transaction and customer telemetry through an interpretable, five-stage analytical pipeline:

```
┌────────────────────────────────────────────────────────┐
│             PUBLIC OBSERVABLE TELEMETRY                │
│  (Failed Transaction / Checkout + Customer History)    │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│               1. FEATURE EXTRACTION                    │
│  • Customer tenure & historical success rate           │
│  • Ticket size anomaly ratio (Amount / AvgAmount)      │
│  • Normalized failure taxonomy & error semantics       │
│  • Temporal signals (Salary window / Month-end)        │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│               2. DIAGNOSTICS ENGINE                    │
│  • Root-cause classification (TRANSIENT, FUNDS, etc.)  │
│  • Diagnostic Confidence Score ∈ [0.0, 1.0]            │
│  • Risk Signal (LOW | MEDIUM | HIGH | UNKNOWN)         │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│         3. RECOVERABILITY SCORING ENGINE               │
│  • Calibrated recovery probability P(recover) ∈ [0, 1] │
│  • Tier: HIGH (≥0.70) | MEDIUM (0.40–0.70) | LOW (<0.40)│
│  • Feature attributions (±Δ) & natural language factors│
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│            4. ACTION EXPECTED VALUE SCORER             │
│  For each candidate action a ∈ {NO_ACTION, RETRY,      │
│  REMINDER, PAYMENT_LINK, HUMAN_REVIEW}:                │
│  EV(a) = P(success | context, a) × Amount              │
│          - Cost(a) - Friction(a)                       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│             5. RECOMMENDATION ENGINE                   │
│  • Selects optimal action: a* = argmax_{Eligible} EV(a)│
│  • Produces structured ReviveRecommendation payload    │
└────────────────────────────────────────────────────────┘
```

---

## 2. Confidence vs Recoverability: Conceptual Separation

A cornerstone of REVIVE's architectural design is the strict distinction between **Diagnosis Confidence** and **Recoverability Likelihood**:

- **Diagnosis Confidence** ($\text{Conf} \in [0.0, 1.0]$): Quantifies certainty regarding *what failure mode occurred* given available signal clarity.
  - *Example*: A customer with 20 historical transactions experiencing an unambiguous card block yields $\text{Confidence} = 0.96$ (we are certain the card is permanently blocked).
- **Recoverability Score** ($P(\text{recover}) \in [0.0, 1.0]$): Quantifies the probability that *revenue can be successfully captured* through intervention.
  - *Example*: For the permanently blocked card above, $\text{Recoverability} = 0.02$ (the chance of recovering funds on this instrument is near zero).

---

## 3. Mathematical Recoverability Formulation

The recoverability score combines an empirical baseline prior with additive feature contributions:

$$P(\text{recover}) = \text{clamp}\left(\text{Prior}(\text{Category}) + \sum_{i} \Delta_i, \, 0.01, \, 0.99\right)$$

### 3.1. Category Base Priors
- `TRANSIENT_GATEWAY_FAILURE`: $0.85$
- `AUTHENTICATION_FAILURE`: $0.76$
- `PAYMENT_METHOD_FAILURE` (Subscription): $0.80$
- `PAYMENT_METHOD_FAILURE` (One-time): $0.58$
- `BANK_DECLINE` (High Value): $0.74$
- `BANK_DECLINE` (Standard): $0.62$
- `INSUFFICIENT_FUNDS`: $0.60$
- `ABANDONMENT` (OTP / Submission stage): $0.78$
- `ABANDONMENT` (Checkout Started): $0.25$
- `HIGH_RISK`: $0.20$
- `HARD_FAILURE`: $0.02$

### 3.2. Contextual Feature Adjustments ($\Delta$)
1. **Customer Historical Track Record**:
   $$\Delta_{\text{hist}} = (\text{HistoricalSuccessRate} - 0.70) \times 0.35 \quad (\text{if } N_{\text{txns}} \ge 3)$$
2. **Amount Anomaly Dampener**:
   $$\Delta_{\text{amt}} = -\min\left(0.25, \, 0.08 \times \log_2\left(\frac{\text{Amount}}{\text{AvgAmount}}\right)\right) \quad (\text{if Ratio} \ge 3.0)$$
3. **Liquidity Cycle Window (Insufficient Funds)**:
   - Early-month salary window (Days 1–5): $\Delta_{\text{sal}} = +0.15$
   - Month-end shortage window (Days 27–31): $\Delta_{\text{me}} = -0.10$
4. **New Account Uncertainty**: $\Delta_{\text{new}} = -0.08$
5. **Multiple Attempts Exhaustion**: $\Delta_{\text{att}} = -\min(0.30, \, 0.12 \times (\text{AttemptNumber} - 1))$

---

## 4. Action Value & Expected Economic Yield ($\text{EV}$)

For every candidate intervention $a \in \{\text{NO\_ACTION}, \text{RETRY}, \text{REMINDER}, \text{PAYMENT\_LINK}, \text{HUMAN\_REVIEW}\}$, the engine computes:

$$\text{EV}(a) = P(\text{success} \mid \text{context}, a) \times \text{Amount} - \text{Cost}(a) - \text{FrictionPenalty}(a)$$

### 4.1. Unit Execution Costs (Synthetic INR)
- `DO_NOTHING`: ₹0.00
- `RETRY`: ₹2.00
- `REMINDER`: ₹1.50
- `PAYMENT_LINK`: ₹3.00
- `HUMAN_REVIEW`: ₹50.00

### 4.2. Action Optimization
The recommendation engine selects the action maximizing Expected Value among logically eligible actions:
$$a^* = \arg\max_{a \in \text{Eligible}} \text{EV}(a)$$
If $\max \text{EV} \le 0.0$, the engine safely defaults to `DO_NOTHING`.

---

## 5. Explainability & Feature Attributions

Every recommendation includes machine-readable factor attributions:

```json
{
  "event_id": "txn_00000412",
  "recommended_action": "PAYMENT_LINK",
  "recoverability_score": 0.782,
  "recoverability_tier": "HIGH",
  "feature_contributions": {
    "base_category_prior": 0.600,
    "historical_success_rate": 0.085,
    "salary_window_liquidity": 0.150,
    "amount_anomaly_dampener": -0.053
  },
  "top_positive_factors": [
    "Timing aligns with early-month salary liquidity cycle",
    "Strong customer track record (92.5% success across 18 transactions)"
  ],
  "top_negative_factors": [
    "Transaction amount is 3.2x higher than customer average"
  ]
}
```

---

## 6. Batch Inference Performance & Benchmark

- **Throughput**: ~1,920 opportunities processed per second on standard CPU.
- **Batch Latency**: ~1.16 seconds for 2,226 failed transactions and abandoned checkouts.
- **Network Dependency**: 100% offline and deterministic; zero external API requests.
