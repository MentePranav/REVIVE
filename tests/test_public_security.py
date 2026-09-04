"""
Security Regression Test Suite for Public Hardening (Phase F).

Verifies:
1. Execution Authorization Boundary (No bypass of recommendation vs authorization vs execution)
2. Deny and Human-Review Execution Blocking
3. High-Risk and Attempt Limit Enforcement
4. Input Validation & Bounds Checking (fail-closed on malformed/oversized input)
5. Path Traversal & Static Asset Confinement
6. Security Headers Presence & Content Security Policy
7. Error Handling & Information Disclosure Prevention
8. Rate Limiting & Abuse Protection (sliding window 429 responses)
9. CORS Policy Conformance
"""

import pytest
from fastapi.testclient import TestClient

from server.app import app
from server.rate_limiter import RATE_LIMITER
from core.config import APP_CONFIG

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Clear in-memory rate limiter buckets before each test."""
    RATE_LIMITER.reset()
    yield
    RATE_LIMITER.reset()


# ==============================================================================
# 1. EXECUTION AUTHORIZATION BOUNDARY
# ==============================================================================

def test_execute_nonexistent_case_returns_404():
    """Attempting to execute an unmapped case ID must return 404."""
    resp = client.post("/api/recovery-cases/fake_case_12345678/execute")
    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data or "detail" in data


def test_execute_deny_case_fails_closed():
    """Cases with policy DENY decision must reject simulated execution and fail closed."""
    resp = client.get("/api/recovery-cases?status=DENY")
    assert resp.status_code == 200
    deny_cases = resp.json()
    if deny_cases:
        target = deny_cases[0]
        resp_exec = client.post(f"/api/recovery-cases/{target['event_id']}/execute")
        assert resp_exec.status_code == 200
        res = resp_exec.json()
        assert res["success"] is False
        assert res["execution_status"] == "BLOCKED"
        assert res["recovered_amount"] == 0.0
        assert "blocked" in res["message"].lower()


def test_execute_human_review_case_fails_closed():
    """Cases requiring HUMAN_REVIEW must refuse automated execution and fail closed."""
    resp = client.get("/api/recovery-cases?status=HUMAN_REVIEW")
    assert resp.status_code == 200
    review_cases = resp.json()
    if review_cases:
        target = review_cases[0]
        resp_exec = client.post(f"/api/recovery-cases/{target['event_id']}/execute")
        assert resp_exec.status_code == 200
        res = resp_exec.json()
        assert res["success"] is False
        assert res["execution_status"] == "BLOCKED"
        assert res["recovered_amount"] == 0.0
        assert "blocked" in res["message"].lower()


def test_repeated_execution_is_blocked():
    """Once executed, re-executing the same case must be blocked by safety state recheck."""
    resp = client.get("/api/recovery-cases")
    cases = resp.json()
    allowed = next((c for c in cases if c["has_authorization"] and c["policy_decision"] == "ALLOW" and c["execution_status"] == "PENDING"), None)

    if allowed:
        event_id = allowed["event_id"]
        # First execution
        first_resp = client.post(f"/api/recovery-cases/{event_id}/execute")
        assert first_resp.status_code == 200

        # Second execution attempt must be blocked
        second_resp = client.post(f"/api/recovery-cases/{event_id}/execute")
        assert second_resp.status_code == 200
        res2 = second_resp.json()
        assert res2["execution_status"] == "BLOCKED"
        assert res2["success"] is False


# ==============================================================================
# 2. INPUT VALIDATION & FAIL-CLOSED BEHAVIOR
# ==============================================================================

def test_simulation_run_invalid_seed_bounds():
    """Seed < 0 or > 2147483647 must fail with 422."""
    resp_neg = client.post("/api/simulation/run", json={"seed": -1, "size": 100})
    assert resp_neg.status_code == 422

    resp_huge = client.post("/api/simulation/run", json={"seed": 999999999999, "size": 100})
    assert resp_huge.status_code == 422


def test_simulation_run_invalid_size_bounds():
    """Batch size <= 0 or > 10000 must fail with 422."""
    resp_zero = client.post("/api/simulation/run", json={"seed": 42, "size": 0})
    assert resp_zero.status_code == 422

    resp_oversized = client.post("/api/simulation/run", json={"seed": 42, "size": 50000})
    assert resp_oversized.status_code == 422


def test_simulation_run_oversized_scenario_string():
    """Scenario strings exceeding 50 chars must fail with 422."""
    resp = client.post("/api/simulation/run", json={"seed": 42, "size": 100, "scenario": "A" * 100})
    assert resp.status_code == 422


def test_simulation_run_malformed_json():
    """Malformed non-JSON body must return 422."""
    resp = client.post("/api/simulation/run", content="not-a-valid-json", headers={"Content-Type": "application/json"})
    assert resp.status_code == 422


def test_recovery_cases_query_length_validation():
    """Oversized query parameters must be rejected with 422."""
    resp = client.get("/api/recovery-cases?search=" + "X" * 300)
    assert resp.status_code == 422


def test_audit_log_limit_bounds():
    """Audit query limit > 500 or < 1 must be rejected with 422."""
    resp_neg = client.get("/api/audit?limit=0")
    assert resp_neg.status_code == 422

    resp_huge = client.get("/api/audit?limit=1000")
    assert resp_huge.status_code == 422


def test_event_id_path_traversal_characters_rejected():
    """Event IDs with path traversal or invalid characters must fail safely."""
    resp = client.get("/api/recovery-cases/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code in (400, 404)


# ==============================================================================
# 3. PATH TRAVERSAL & STATIC FILE SERVING
# ==============================================================================

def test_static_path_traversal_blocked():
    """Attempts to traverse out of static assets directory must return 404."""
    traversal_paths = [
        "/static/../.env",
        "/static/..%2F.env",
        "/static/..%5C.env",
        "/static/../../requirements.txt",
        "/static/../server/app.py",
    ]
    for path in traversal_paths:
        resp = client.get(path)
        assert resp.status_code in (404, 400), f"Path {path} returned {resp.status_code}"


def test_nonexistent_static_asset_returns_404():
    """Requesting non-existent static file returns 404 cleanly."""
    resp = client.get("/static/non_existent_bundle_123.js")
    assert resp.status_code == 404


# ==============================================================================
# 4. SECURITY HEADERS
# ==============================================================================

def test_security_headers_present_on_html_and_api():
    """Required security headers must be present on all responses."""
    endpoints = ["/", "/control-center", "/demo", "/api/health", "/api/overview"]
    for ep in endpoints:
        resp = client.get(ep)
        assert resp.status_code == 200
        headers = resp.headers

        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert headers.get("X-Frame-Options") == "SAMEORIGIN"
        assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "Content-Security-Policy" in headers
        assert "Permissions-Policy" in headers


# ==============================================================================
# 5. ERROR DISCLOSURE PREVENTION
# ==============================================================================

def test_internal_errors_do_not_leak_stack_traces():
    """Error responses must not expose Python tracebacks or local paths."""
    resp = client.get("/api/recovery-cases/%00invalid")
    assert resp.status_code in (400, 404, 422)
    body = resp.text
    assert "Traceback (most recent call last)" not in body
    assert "C:\\Users\\" not in body
    assert "/Users/" not in body
    assert "antigravity" not in body.lower()


# ==============================================================================
# 6. IN-PROCESS RATE LIMITING
# ==============================================================================

def test_rate_limiter_blocks_excessive_simulation_runs():
    """Rate limiter must enforce limit on /api/simulation/run and return 429."""
    # Simulation limit is 30 / minute
    client_ip = "127.0.0.1"

    # Rapidly send 32 requests
    hit_429 = False
    for i in range(35):
        resp = client.post("/api/simulation/run", json={"seed": 42, "size": 10})
        if resp.status_code == 429:
            hit_429 = True
            assert "Retry-After" in resp.headers
            assert "rate limit exceeded" in resp.text.lower()
            break

    assert hit_429, "Rate limiter should have triggered 429 within 35 requests"


# ==============================================================================
# 7. CORS POLICY CONFORMANCE
# ==============================================================================

def test_cors_preflight_and_wildcard_no_credentials():
    """CORS requests must not expose wildcard credentials."""
    resp = client.options(
        "/api/overview",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        }
    )
    # If Access-Control-Allow-Origin is '*', Access-Control-Allow-Credentials must not be 'true'
    allow_origin = resp.headers.get("Access-Control-Allow-Origin")
    allow_creds = resp.headers.get("Access-Control-Allow-Credentials")
    if allow_origin == "*":
        assert allow_creds != "true"
