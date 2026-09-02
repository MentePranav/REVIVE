# REVIVE — Autonomous Revenue Recovery Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-177%20passed-brightgreen.svg)]()
[![Buildathon Track](https://img.shields.io/badge/Razorpay%20AI%20Buildathon-Track%203%3A%20AI%20Revenue%20Recovery-orange.svg)]()
[![Security Boundary](https://img.shields.io/badge/Security-Zero--Trust%20Fail--Closed-red.svg)]()

> **"Recover more revenue. Intervene less. Stay in control."**

**REVIVE** is an autonomous, context-aware payment recovery and customer lifecycle optimization platform built for the **Razorpay AI Buildathon 2026 (Track 3: AI Revenue Recovery)**.

REVIVE shifts revenue recovery from blind, high-friction retries to an **intelligent diagnosis, recoverability assessment, and zero-trust safety governance** lifecycle.

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12
- Local virtual environment configured with dependencies (`fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx`).

### 2. Launch the Control Center

#### Windows (One-Click)
```cmd
start_revive.bat
```

#### Cross-Platform CLI
```bash
# Activate virtual environment
source .venv/bin/activate  # or .\.venv\Scripts\activate on Windows

# Start server
python -m server.cli --port 8000 --host 127.0.0.1
```

Open your browser to:
- **Interactive Control Center**: [http://localhost:8000](http://localhost:8000)
- **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health & Reproducibility Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

## 🧪 Automated Testing & Verification

Run the full automated test suite covering all 9 phases, zero-trust invariants, property checks, and 20 adversarial edge cases:

```bash
pytest tests/ -v
```
**Status: 177 / 177 passing tests across all modules.**

---

## 🏛️ System Architecture

```text
OBSERVABLE DATA (Phase 2)
  ├── Failed Transactions & Abandoned Checkouts
  └── Customer Payment History & Signals
                ↓
REVIVE INTELLIGENCE (Phase 4)
  ├── Feature Extraction (30+ Signals)
  ├── Failure Diagnosis & Confidence Scoring (P004)
  ├── Net Expected Value (EV) Action Optimization
  └── Decision Explainability & Feature Attributions
                ↓
ZERO-TRUST POLICY & SAFETY ENGINE (Phase 5)
  ├── State Verification & Anti-Double-Recovery (P002)
  ├── Hard Attempt Caps & Fatigue Limits (P003, P007)
  ├── High-Risk Fraud Gate (P005: 0 Leaks Tolerated)
  └── ExecutionAuthorization Token Generation (P010)
                ↓
CONTROLLED EXECUTION SIMULATOR (Phase 6)
  ├── Token Re-Validation & Idempotency Key Lock
  ├── Live State Race-Condition Check
  └── Simulated Recovery Action Dispatch & Audit
                ↓
EVALUATION & OBSERVABILITY (Phases 7–9)
  ├── Multi-Seed Statistical Holdout Benchmarking (50k txns)
  ├── Structured Logging with Sensitive Token Redaction
  ├── Interactive Single-Page Application Control Center
  └── Immutable Chronological Audit Trail
```

---

## 📊 Benchmark Evaluation Highlights (50,000 Holdout Transactions)

Across 5 holdout seeds (Seeds 101–505), REVIVE demonstrated statistically significant superiority over baseline recovery approaches:

| Strategy | Mean Recovered Revenue (INR) | Mean Incremental Revenue (INR) | Overall Recovery Rate | Intervention Precision | Safety & Friction Profile |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`NO_ACTION`** | INR 71,342.40 | INR 0.00 | 0.9% | N/A | Passive observation; captures only organic recoveries. |
| **`NAIVE_RETRY`** | INR 809,172.38 | INR 737,829.97 | 10.9% | 30.8% | Blindly retries; creates 69.2% customer friction on hard declines. |
| **`RULE_BASED`** | INR 3,626,512.01 | INR 3,555,169.60 | 48.6% | 69.5% | Heuristic rules; lacks zero-trust governance & fraud risk gates. |
| **`REVIVE (Ours)`** | **INR 2,726,857.62** | **INR 2,655,515.22** | **36.5%** | **56.0%** | **Contextual optimization + 30.4% Human Review escalation + 2-attempt cap.** |

---

## 📚 Project Documentation

- [System Architecture Specification](docs/architecture.md)
- [Reliability & Observability Guide](docs/reliability.md)
- [Hackathon Evaluator Demo Checklist](docs/demo-checklist.md)
- [Comprehensive Holdout Benchmark Report (50k txns)](experiments/benchmark_5seeds_10k/BENCHMARK_REPORT.md)

---

## 🛡️ Security & Evaluation Boundary Disclosures

- **Simulation Mode**: REVIVE operates exclusively in a statistically controlled, deterministic local simulation environment. No real banking credentials or live payments are charged.
- **Fail-Closed Principle**: Any schema anomaly, stale authorization token, or ambiguous confidence automatically fails closed without executing automated actions.
