"""
End-to-End full demo and safety boundary test for REVIVE Control Center.
"""

from fastapi.testclient import TestClient
import pytest

from server.app import app

client = TestClient(app)


def test_end_to_end_demo_workflow():
    """
    Validates complete evaluator workflow:
    1. Initialize fresh simulation session
    2. Read Overview KPIs
    3. Inspect Recovery Cases queue
    4. Drill down into an ALLOW case, verify factors and checklist
    5. Execute recovery via authorized endpoint
    6. Verify audit event was logged
    7. Verify DENY case cannot be executed by client
    """
    # Step 1: Run Simulation with 200 transactions
    sim_resp = client.post("/api/simulation/run", json={"seed": 101, "size": 200, "scenario": "balanced"})
    assert sim_resp.status_code == 200
    summary = sim_resp.json()
    assert summary["total_transactions"] == 200
    assert summary["revenue_at_risk"] > 0

    # Step 2: Query Overview
    overview = client.get("/api/overview").json()
    assert overview["total_failed_opportunities"] == summary["total_failed_opportunities"]

    # Step 3: Fetch Cases
    cases = client.get("/api/recovery-cases").json()
    assert len(cases) > 0

    # Step 4: Drill down into an ALLOW case
    allow_case = next((c for c in cases if c["policy_decision"] == "ALLOW" and c["has_authorization"]), None)
    assert allow_case is not None, "Expected at least one ALLOW case in demo batch"

    detail = client.get(f"/api/recovery-cases/{allow_case['event_id']}").json()
    assert detail["can_execute"] is True
    assert isinstance(detail["top_positive_factors"], list)
    assert any(item["passed"] for item in detail["safety_checklist"])

    # Step 5: Execute recovery
    exec_resp = client.post(f"/api/recovery-cases/{allow_case['event_id']}/execute")
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["execution_status"] in ("EXECUTED", "BLOCKED")

    # Step 6: Verify Audit Trail
    audits = client.get("/api/audit?limit=20").json()
    assert len(audits) > 0

    # Step 7: Check DENY or HUMAN_REVIEW case cannot be executed
    restricted_case = next((c for c in cases if c["policy_decision"] in ("DENY", "HUMAN_REVIEW")), None)
    if restricted_case:
        r_detail = client.get(f"/api/recovery-cases/{restricted_case['event_id']}").json()
        assert r_detail["can_execute"] is False

        # Attempting execution on restricted case fails safely
        r_exec = client.post(f"/api/recovery-cases/{restricted_case['event_id']}/execute").json()
        assert r_exec["success"] is False
        assert r_exec["execution_status"] == "BLOCKED"
