# REVIVE — Reliability, Observability & Reproducibility Architecture

## 1. Executive Summary & Design Principles

REVIVE (Autonomous Revenue Recovery Agent) is engineered with zero-trust execution boundaries, deterministic evaluation pipelines, and fail-safe error handling.

### Core Architectural Principles
1. **Zero-Trust Boundary**: Intelligence models and user-facing clients can only recommend or request actions; only the `PolicyEngine` can authorize actions, and the `ControlledExecutor` validates validated policy-issued tokens before simulating any state transition.
2. **Fail-Closed Default**: In any condition involving missing data, malformed payloads, ambiguous confidence, or unhandled exceptions, REVIVE fails closed: `NO ACTION IS EXECUTED`.
3. **Reproducibility by Construction**: All synthetic data generation, ML feature extraction, rule evaluation, and holdout experimentation operate under explicit pseudo-random seeds. A validated policy-issued SHA-256 reproducibility fingerprint is computed across configuration, engine versions, and dataset seeds.
4. **Deterministic Observability**: Every lifecycle stage emits structured JSON log events with correlation IDs (`X-Correlation-ID`) and an immutable in-memory audit log. Sensitive customer tokens and API credentials are automatically redacted (`[REDACTED]`).

---

## 2. Standardized Error Taxonomy

All internal domain exceptions inherit from `ReviveError` (`core.errors.ReviveError`) and map to standardized error categories:

| Error Class | Category Code | HTTP Status | Meaning |
| :--- | :--- | :--- | :--- |
| `InputError` | `INPUT_ERROR` | 400 | Missing required transaction fields, negative amounts, or malformed schema. |
| `PolicyError` | `POLICY_ERROR` | 400 | Safety rule violation (e.g., attempting action on already-resolved payment). |
| `AuthorizationError`| `AUTHORIZATION_ERROR` | 403 | Invalid, forged, expired, or mismatched execution authorization token. |
| `ExecutionError` | `EXECUTION_ERROR` | 400 | Internal execution boundary fault or attempt cap violation. |
| `SimulationError` | `SIMULATION_ERROR` | 500 | Synthetic generator inconsistency or corrupt distribution state. |
| `EvaluationError` | `EVALUATION_ERROR` | 500 | Benchmark runner failure, missing holdout split, or accounting mismatch. |
| `SystemError` | `SYSTEM_ERROR` | 500 | Unhandled runtime exception; sanitized before returning to client. |

---

## 3. Structured Logging & Sensitive Data Redaction

Logging is centralized in `core.logging` and formats all log events as newline-delimited JSON with standard fields:
- `timestamp`: ISO-8601 UTC timestamp
- `level`: `INFO`, `WARNING`, `ERROR`
- `logger`: Subsystem identifier (e.g. `revive.policy`, `revive.executor`, `revive.server`)
- `correlation_id`: Request correlation ID
- `event_id`: Transaction or checkout identifier
- `message`: Human-readable summary

### Automated Redaction Engine
Any dictionary or payload containing sensitive key identifiers (e.g. `api_key`, `secret`, `auth_token`, `password`, `bearer_token`, `card_number`, `cvv`) is automatically sanitized to `[REDACTED]` prior to logging.

---

## 4. Reproducibility Fingerprinting

To ensure scientific credibility for evaluations, REVIVE computes a SHA-256 digest over runtime parameters:
```python
fingerprint = APP_CONFIG.compute_reproducibility_fingerprint(seed=42, size=100)
```
The health check endpoint (`GET /api/health`) provides this fingerprint alongside system versions and environment verification status.

---

## 5. Startup & Environment Validation

`EnvironmentValidator` (`core.environment_validator.py`) inspects the host runtime at launch:
- Python 3.10+ interpreter check.
- Required library presence (`fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx`).
- Filesystem layout verification (directories for simulator, agent, policy, execution, evaluation, server, docs, experiments, tests).
- Zero external cloud requirement: Confirms `cloud_credentials_required: False`.
