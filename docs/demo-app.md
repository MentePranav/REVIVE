# REVIVE — Interactive Revenue Recovery Control Center & Demo Application

## 1. Overview & Purpose

The **REVIVE Interactive Control Center** is a high-density, evaluator-facing web application built to demonstrate the full end-to-end autonomous revenue recovery lifecycle:

$$\text{Revenue at Risk} \longrightarrow \text{Diagnosis} \longrightarrow \text{Scoring} \longrightarrow \text{Policy Safety Gate} \longrightarrow \text{Authorized Execution} \longrightarrow \text{Outcome Measurement}$$

> [!IMPORTANT]
> **Synthetic Simulation Notice**: All financial metrics, customer histories, and recovery outcomes shown in the Control Center represent controlled synthetic benchmarks in a simulation-only prototype.

---

## 2. Technology Stack & Architecture

```
[ Frontend: Rich Fintech Single-Page Application (SPA) ]
  • Dark-mode dashboard with KPI metrics & Action Breakdown
  • Filterable & sortable Recovery Cases queue
  • Drilldown modal: Contextual Diagnosis, EV ranking, Safety Checklist
  • Safety & Governance view (P001-P010 rule hierarchy)
  • Benchmark comparative analysis (REVIVE vs. Baselines)
  • Immutable Audit Trail Explorer
                  │
                  ▼ (REST JSON API)
┌────────────────────────────────────────────────────────┐
│            BACKEND REST API SERVER (FastAPI)           │
│  GET  /api/health                                      │
│  GET  /api/overview                                    │
│  POST /api/simulation/run                              │
│  GET  /api/recovery-cases                              │
│  GET  /api/recovery-cases/{id}                         │
│  POST /api/recovery-cases/{id}/execute                 │
│  GET  /api/safety                                      │
│  GET  /api/benchmark                                   │
│  GET  /api/audit                                       │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│             EXISTING BACKEND ENGINE LAYERS             │
│  • Phase 2: Synthetic Generator & Simulator Context    │
│  • Phase 4: Contextual Diagnosis & Expected Value      │
│  • Phase 5: Zero-Trust Policy Governance Engine        │
│  • Phase 6: Controlled Recovery Executor & Audit Log   │
│  • Phase 7: Holdout Benchmarking & Evaluation Engine   │
└────────────────────────────────────────────────────────┘
```

---

## 3. Zero-Trust Safety Boundary

The frontend is strictly a presentation layer and **cannot manufacture execution authorizations**:
1. When clicking **"Execute Simulated Recovery"**, the UI dispatches a `POST /api/recovery-cases/{id}/execute` request.
2. The backend re-validates the policy-issued `ExecutionAuthorization`.
3. The backend verifies live payment state (ensuring payment has not been captured out-of-band).
4. The action is executed strictly through Phase 6 `ControlledExecutor` and an immutable audit event is recorded.
5. If policy decision is `DENY` or `HUMAN_REVIEW`, automated execution is hard-blocked.

---

## 4. Local Quickstart Instructions (Windows)

### 4.1. Start the Control Center Web Server
```powershell
python -m server.cli --port 8000 --host 127.0.0.1
```

### 4.2. Access the Application
Open your browser and navigate to:
* **Interactive Dashboard**: `http://localhost:8000`
* **Swagger OpenAPI Docs**: `http://localhost:8000/docs`

---

## 5. Step-by-Step Evaluator Demo Walkthrough

1. **Launch Simulation**:
   - In the top bar, select **Batch Size** (`100`, `1,000`, or `10,000`) and click `⚡ Run Recovery Simulation`.
2. **Review Overview KPIs**:
   - Inspect **Revenue at Risk**, **Revenue Recovered**, and **Incremental Revenue ($\Delta R$)**.
   - Note the **Action Breakdown** showing why REVIVE does not blindly retry every failed payment.
3. **Inspect Recovery Cases**:
   - Switch to the **Recovery Cases** tab.
   - Filter by status (`Recovered`, `Policy Blocked`, `Human Review`).
   - Click `Inspect` on any transaction to open the **Recovery Case Drilldown**.
4. **Examine Intelligence & Governance**:
   - In the modal, review the **Phase 4 Root-Cause Diagnosis** and confidence percentage.
   - Check the **Action Expected Value (EV)** ranking table.
   - Verify the **Phase 5 Safety Gate Checklist** showing rule-by-rule evaluation ($P001$ to $P008$).
5. **Execute Simulated Recovery**:
   - On an authorized case (`ALLOW`), click `⚡ Execute Simulated Recovery`.
   - Observe live execution dispatch, outcome resolution, and recorded audit event.
6. **Compare Benchmark Strategies**:
   - Switch to the **Benchmark** tab to compare REVIVE's performance against `NO_ACTION`, `NAIVE_RETRY`, and `RULE_BASED`.
7. **Inspect Audit Trail**:
   - Switch to the **Audit Log** tab to view the complete chronological sequence of timestamped lifecycle events.
