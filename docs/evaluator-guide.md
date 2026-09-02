# REVIVE — Buildathon Evaluator Quick-Start Guide

Welcome to the **REVIVE (Autonomous Revenue Recovery Agent)** repository. This concise guide directs evaluators to the most important technical evidence and demonstrations in the repository.

---

## Recommended 5-Step Evaluation Sequence

```text
1. Read Overview      --> README.md & docs/revive-architecture.svg
2. Launch Server      --> start_revive.bat (or python -m server.cli --port 8000)
3. Test Demo in UI    --> http://localhost:8000 (Follow docs/demo-runbook.md)
4. Inspect Evidence   --> experiments/benchmark_5seeds_10k/BENCHMARK_REPORT.md
5. Verify Test Suite  --> pytest tests/ -v (177/177 passing tests)
```

---

## 1. Step 1 — Review Architecture & Core Concept (1 Minute)
- **[README.md](file:///C:/Users/Home/Projects/REVIVE/README.md)**: Explains the Track 3 problem (blind retries vs. context-aware recovery) and core thesis.
- **[docs/revive-architecture.svg](file:///C:/Users/Home/Projects/REVIVE/docs/revive-architecture.svg)**: Visualizes the physical separation between AI intelligence and Zero-Trust Policy authorization.

---

## 2. Step 2 — Run the Interactive Control Center (2 Minutes)
1. Double-click `start_revive.bat` or run:
   ```powershell
   .\.venv\Scripts\python.exe -m server.cli --port 8000
   ```
2. Navigate to **[http://localhost:8000](http://localhost:8000)**.
3. Open the **Recovery Cases** tab and click **Inspect** on any case:
   - **Phase 4 Intelligence**: View root-cause diagnosis, confidence score, and Net Expected Value ($EV$) ranking across actions.
   - **Phase 5 Safety Gate**: Review the 7-item safety checklist and verify that only approved cases receive an `ExecutionAuthorization` token.
   - **Phase 6 Controlled Execution**: Click **Execute Simulated Recovery** and observe state re-validation and outcome recording.

---

## 3. Step 3 — Inspect Statistical Holdout Benchmark Evidence (1 Minute)
- Navigate to the **Benchmark** tab in the web interface or open:
  **[experiments/benchmark_5seeds_10k/BENCHMARK_REPORT.md](file:///C:/Users/Home/Projects/REVIVE/experiments/benchmark_5seeds_10k/BENCHMARK_REPORT.md)**
- Review the 4-way comparative evaluation across **50,000 synthetic holdout transactions**:
  - `NO_ACTION`: INR 71,342.40 (0.94% organic recovery)
  - `NAIVE_RETRY`: INR 809,172.38 (30.82% precision; 69.18% friction)
  - `RULE_BASED`: INR 3,626,512.01 (Unconstrained; lacks fraud gates)
  - **`REVIVE`**: **INR 2,726,857.62 (Incremental ΔR: INR 2,655,515.22; 55.99% precision; 0 fraud leaks)**

---

## 4. Step 4 — Verify Deterministic Reproducibility (30 Seconds)
- Open **[http://localhost:8000/api/health](http://localhost:8000/api/health)**:
  - Verify `"status": "healthy"`.
  - Check the cryptographic SHA-256 reproducibility fingerprint: `"35b2e65d2efaa521"`.

---

## 5. Step 5 — Run the Full Automated Test Suite (30 Seconds)
Execute all 177 unit, integration, property, and adversarial tests:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```
- **Coverage**: 11 simulator tests, 17 baseline tests, 26 intelligence agent tests, 22 policy engine tests, 35 execution tests, 26 holdout experiment tests, 12 server API tests, 8 end-to-end tests, 10 observability tests, and 20 adversarial edge case tests.
- **Expected Result**: `177 passed in ~9.8s`.
