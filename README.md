# REVIVE — Autonomous Revenue Recovery Agent

[![Status](https://img.shields.io/badge/Status-Under%20Active%20Development%20(Phase%201)-orange.svg)](#current-development-status)
[![Track](https://img.shields.io/badge/Track-AI%20Revenue%20Recovery-blue.svg)](#)
[![Hackathon](https://img.shields.io/badge/Razorpay%20AI%20Buildathon-2026-green.svg)](#)

> **REVIVE** is an event-driven agentic system that identifies recoverable failed payments, determines the safest economically optimal recovery action, executes bounded recovery interventions, and measures incremental revenue recovered against strong baselines.

---

## Current Development Status

> [!NOTE]
> **Under active development — Phase 1: Project Initialization & Architecture**
>
> The project is currently in **Phase 1**. Core architecture, safety invariants, repository isolation, environment verification, and development roadmaps are established. Functional modules (simulator, agent, policy engine, evaluation engine, frontend dashboard) will be implemented iteratively across subsequent phases.

---

## The Problem

Payment failures represent a massive source of revenue leakage for digital businesses and subscription merchants:
- **Indiscriminate Retries**: Traditional payment recovery engines blindly retry failed transactions, causing bank penalties, gateway throttling, and elevated dispute rates.
- **Customer Fatigue**: Intrusive, repetitive dunning notifications frustrate customers and drive voluntary churn.
- **Suboptimal Recovery Timing**: Retrying a transaction at the wrong time (e.g. before payday, during banking maintenance windows) wastes limited retry attempts.
- **Lack of Economic Grounding**: Standard recovery systems do not quantify the expected value ($EV$) of an intervention versus its churn risk and communication cost.

---

## The REVIVE Solution

REVIVE introduces an intelligent, autonomous recovery loop that balances recovery probability against customer experience and financial risk.

```
PAYMENT EVENT
      ↓
    DETECT
      ↓
   DIAGNOSE
      ↓
ESTIMATE RECOVERABILITY
      ↓
SELECT ACTION
      ↓
 POLICY GATE (Deterministic Safety Filter)
      ↓
   EXECUTE (Bounded Interventions)
      ↓
OBSERVE OUTCOME
      ↓
STOP / RETRY / ESCALATE
      ↓
    AUDIT
```

### Core Architecture Principle: Separation of Reasoning & Policy

```
AI Recommendation ──► Deterministic Policy Engine ──► Allowed / Blocked / Escalated ──► Action Executor
```

The system strictly enforces that **AI reasoning never possesses direct financial execution authority**. Every candidate action proposed by the LLM must pass through deterministic policy gates that enforce hard business rules (cooldowns, retry limits, customer fatigue limits, discount caps).

---

## Repository Structure

```text
REVIVE/
│
├── README.md               # Project overview and status
├── .gitignore              # Git ignore rules
├── .env.example            # Environment configuration template
│
├── docs/                   # System design and specifications
│   ├── architecture.md     # Detailed technical architecture specification
│   └── development-plan.md # 12-phase engineering roadmap
│
├── backend/                # FastAPI backend & webhook handlers (Phase 8+)
├── frontend/               # React + TypeScript dashboard (Phase 9+)
├── simulator/              # Synthetic transaction & persona simulator (Phase 2)
├── agent/                  # AI reasoning, diagnosis & execution loop (Phases 4, 6)
├── policy/                 # Deterministic policy & safety engine (Phase 5)
├── evaluation/             # Ground-truth benchmarking & baselines (Phases 3, 7)
├── tests/                  # Unit, integration & adversarial test suites (Phase 11)
├── scripts/                # Utility and demo scripts (Phase 12)
└── data/                   # Data directory for simulations and benchmarks
```

---

## Technology Stack

- **Backend & Core Engine**: Python 3.13 + FastAPI
- **Frontend & Dashboard**: React + TypeScript + Vite
- **Database**: SQLite (local development / testing) with path to PostgreSQL
- **AI & Reasoning**: Configurable LLM provider (Gemini / OpenAI API) with structured output validation and deterministic heuristic fallback
- **Testing**: `pytest` (backend / policy / evaluation) and component test runners

---

## Phased Development Roadmap

1. **Phase 1: Project Initialization & Architecture** *(Current)*
2. **Phase 2: Synthetic Data Simulator**
3. **Phase 3: Naive & Rule-Based Baselines**
4. **Phase 4: REVIVE Diagnosis & Recovery Scoring**
5. **Phase 5: Policy & Safety Engine**
6. **Phase 6: Agent Execution Loop**
7. **Phase 7: Evaluation & Held-Out Testing**
8. **Phase 8: Razorpay Test-Mode Integration & Webhooks**
9. **Phase 9: Frontend Dashboard**
10. **Phase 10: Audit Explorer & Explainability**
11. **Phase 11: Testing & Adversarial Evaluation**
12. **Phase 12: Demo Mode & Final Polish**

Detailed specifications for each phase are documented in [`docs/development-plan.md`](file:///C:/Users/Home/Projects/REVIVE/docs/development-plan.md).

---

## Getting Started (Phase 1)

### Prerequisites
- Python 3.11+
- Node.js v20+
- Git

### Initial Setup
1. Clone or navigate to the repository:
   ```bash
   cd C:/Users/Home/Projects/REVIVE
   ```
2. Copy configuration template:
   ```bash
   cp .env.example .env
   ```
3. Follow upcoming phase guides as modules are incrementally implemented.
