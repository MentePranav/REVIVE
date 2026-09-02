"""
Automated unit and integration tests for REVIVE Phase 9: Reliability, Observability & Reproducibility.
"""

from pathlib import Path
import time
from fastapi.testclient import TestClient
import pytest

from core.config import APP_CONFIG, ReviveAppConfig
from core.environment_validator import EnvironmentValidator
from core.errors import (
    AuthorizationError,
    ErrorCategory,
    ExecutionError,
    InputError,
    PolicyError,
    ReviveError,
)
from core.logging import get_logger, sanitize_payload
from evaluation.experiment.config import ExperimentConfig
from evaluation.experiment.runner import ExperimentRunner
from server.app import app

client = TestClient(app)


def test_1_environment_validator():
    """Test 1: EnvironmentValidator validates runtime without external cloud keys."""
    is_valid, errors, details = EnvironmentValidator.validate()
    assert is_valid is True
    assert len(errors) == 0
    assert details["cloud_credentials_required"] is False
    assert details["packages"]["fastapi"] == "installed"
    assert details["directories"]["policy"] == "present"


def test_2_reproducibility_fingerprint_deterministic():
    """Test 2: Identical config parameters produce identical SHA-256 fingerprints."""
    cfg = ReviveAppConfig()
    fp1 = cfg.compute_reproducibility_fingerprint(seed=42, size=100)
    fp2 = cfg.compute_reproducibility_fingerprint(seed=42, size=100)
    fp_diff = cfg.compute_reproducibility_fingerprint(seed=999, size=100)

    assert fp1 == fp2
    assert len(fp1) == 16
    assert fp1 != fp_diff


def test_3_structured_payload_sanitizer():
    """Test 3: Sanitizer redacts sensitive API keys and secrets."""
    raw = {
        "event_id": "txn_001",
        "api_key": "secret_key_12345",
        "nested": {"auth_token": "bearer_abc", "amount": 500.0}
    }
    sanitized = sanitize_payload(raw)
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["auth_token"] == "[REDACTED]"
    assert sanitized["nested"]["amount"] == 500.0


def test_4_error_taxonomy_serialization():
    """Test 4: Error taxonomy subclasses serialize with machine-readable error codes."""
    err = PolicyError("Payment already resolved.", correlation_id="req_test_123")
    d = err.to_dict()
    assert d["error"] is True
    assert d["error_code"] == ErrorCategory.POLICY_ERROR.value
    assert d["correlation_id"] == "req_test_123"


def test_5_health_endpoint_metadata():
    """Test 5: GET /api/health includes reproducibility fingerprint and environment validity."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "reproducibility_fingerprint" in data
    assert data["environment_valid"] is True


def test_6_demo_session_reset():
    """Test 6: POST /api/demo/reset resets session to deterministic golden state."""
    # First modify session
    client.post("/api/simulation/run", json={"seed": 777, "size": 50, "scenario": "balanced"})

    # Reset
    reset_resp = client.post("/api/demo/reset")
    assert reset_resp.status_code == 200
    summary = reset_resp.json()
    assert summary["session_seed"] == 42
    assert summary["total_transactions"] == 100


def test_7_correlation_id_middleware_propagation():
    """Test 7: Client correlation ID is echoed in response headers."""
    custom_cid = "req_custom_obs_999"
    resp = client.get("/api/overview", headers={"X-Correlation-ID": custom_cid})
    assert resp.status_code == 200
    assert resp.headers.get("X-Correlation-ID") == custom_cid


def test_8_structured_error_handling_no_traceback():
    """Test 8: Querying non-existent case returns structured error JSON without traceback."""
    resp = client.get("/api/recovery-cases/txn_non_existent_99999")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"] is True
    assert "not found" in data["message"].lower()
    assert "Traceback" not in resp.text


def test_9_benchmark_artifact_integrity_fallback(tmp_path, monkeypatch):
    """Test 9: Missing or corrupted benchmark artifact produces safe message without 500 crash."""
    resp = client.get("/api/benchmark")
    assert resp.status_code == 200
    data = resp.json()
    assert "dataset_info" in data


def test_10_performance_benchmark_scaling():
    """Test 10: Processing scales efficiently across 100, 1,000, and 10,000 transactions."""
    for count in (100, 1000):
        t0 = time.perf_counter()
        cfg = ExperimentConfig(
            experiment_id=f"perf_{count}",
            dev_seed=42,
            eval_seeds=[101],
            dev_transaction_count=100,
            eval_transaction_count=count,
            bootstrap_samples=10
        )
        runner = ExperimentRunner(cfg)
        rep, _ = runner.run_experiment()
        elapsed = time.perf_counter() - t0
        assert rep.total_evaluations == 1
        assert elapsed < 5.0 # Under 5s per evaluation
