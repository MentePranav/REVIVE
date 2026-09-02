"""
Integration tests for the REVIVE Interactive Control Center FastAPI Server API.
"""

from fastapi.testclient import TestClient
import pytest

from server.app import app

client = TestClient(app)


def test_1_health_check_endpoint():
    """Test 1: GET /api/health returns 200 and healthy status."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "REVIVE" in data["service"]


def test_2_overview_endpoint():
    """Test 2: GET /api/overview returns complete summary metrics."""
    resp = client.get("/api/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_transactions"] > 0
    assert data["total_failed_opportunities"] > 0
    assert data["revenue_at_risk"] > 0.0
    assert "action_breakdown" in data
    assert "safety_metrics" in data
    assert "SYNTHETIC" in data["disclaimer"]


def test_3_run_simulation_custom_seed():
    """Test 3: POST /api/simulation/run runs new simulation batch."""
    payload = {"seed": 999, "size": 150, "scenario": "balanced"}
    resp = client.post("/api/simulation/run", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_seed"] == 999
    assert data["total_transactions"] == 150


def test_4_list_recovery_cases():
    """Test 4: GET /api/recovery-cases returns list of cases."""
    resp = client.get("/api/recovery-cases")
    assert resp.status_code == 200
    cases = resp.json()
    assert isinstance(cases, list)
    assert len(cases) > 0

    first = cases[0]
    assert "event_id" in first
    assert "amount" in first
    assert "diagnosis" in first
    assert "policy_decision" in first
    assert "execution_status" in first


def test_5_filter_recovery_cases():
    """Test 5: Filtering by status and action returns matching subset."""
    resp_all = client.get("/api/recovery-cases")
    total_len = len(resp_all.json())

    resp_action = client.get("/api/recovery-cases?action=RETRY")
    assert resp_action.status_code == 200
    cases_retry = resp_action.json()
    for c in cases_retry:
        assert c["recommended_action"] == "RETRY"


def test_6_get_recovery_case_detail():
    """Test 6: GET /api/recovery-cases/{id} returns comprehensive intelligence & checklist."""
    resp_list = client.get("/api/recovery-cases")
    cases = resp_list.json()
    assert len(cases) > 0
    event_id = cases[0]["event_id"]

    resp = client.get(f"/api/recovery-cases/{event_id}")
    assert resp.status_code == 200
    d = resp.json()

    assert d["event_id"] == event_id
    assert "diagnosis_confidence" in d
    assert "recoverability_score" in d
    assert "action_scores" in d
    assert len(d["action_scores"]) > 0
    assert "safety_checklist" in d
    assert len(d["safety_checklist"]) > 0
    assert "top_positive_factors" in d


def test_7_get_non_existent_case_returns_404():
    """Test 7: GET /api/recovery-cases/invalid_id returns 404."""
    resp = client.get("/api/recovery-cases/invalid_txn_999999")
    assert resp.status_code == 404


def test_8_execute_recovery_on_allowed_case():
    """Test 8: POST /api/recovery-cases/{id}/execute re-validates authorization and executes."""
    resp_list = client.get("/api/recovery-cases")
    cases = resp_list.json()

    # Find an allowed case with authorization
    allowed_case = next((c for c in cases if c["has_authorization"] and c["policy_decision"] == "ALLOW"), None)
    if allowed_case:
        resp = client.post(f"/api/recovery-cases/{allowed_case['event_id']}/execute")
        assert resp.status_code == 200
        res = resp.json()
        assert res["execution_status"] in ("EXECUTED", "BLOCKED")


def test_9_execute_recovery_on_non_existent_case_returns_404():
    """Test 9: Executing non-existent case returns 404."""
    resp = client.post("/api/recovery-cases/invalid_txn_88888/execute")
    assert resp.status_code == 404


def test_10_safety_dashboard_endpoint():
    """Test 10: GET /api/safety returns valid policy metrics."""
    resp = client.get("/api/safety")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_checks"] > 0
    assert "rule_distributions" in data
    assert "blocks_breakdown" in data


def test_11_audit_log_endpoint():
    """Test 11: GET /api/audit returns chronological audit items."""
    resp = client.get("/api/audit?limit=50")
    assert resp.status_code == 200
    audits = resp.json()
    assert isinstance(audits, list)
    assert len(audits) > 0
    assert "audit_id" in audits[0]
    assert "event_type" in audits[0]


def test_12_benchmark_endpoint():
    """Test 12: GET /api/benchmark returns evaluation comparison."""
    resp = client.get("/api/benchmark")
    assert resp.status_code == 200
    data = resp.json()
    assert "strategies" in data
