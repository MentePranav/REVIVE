"""
FastAPI Application for the REVIVE Interactive Revenue Recovery Control Center.
Serves REST APIs and the rich Single-Page Application (SPA) frontend.
"""

from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from server.models import (
    AuditLogItem,
    BenchmarkResponse,
    ExecuteRecoveryResponse,
    RecoveryCaseDetailResponse,
    RecoveryCaseListItem,
    SafetyDashboardResponse,
    SimulationRequest,
    SimulationSummaryResponse,
)
from server.state import ServerStateManager

app = FastAPI(
    title="REVIVE — Autonomous Revenue Recovery Control Center",
    version="1.0.0",
    description="Interactive control center, decision explainability, and safety audit dashboard for REVIVE."
)

# Enable CORS for local cross-origin development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global In-Memory State Coordinator
state = ServerStateManager()

# Static Assets Path
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>REVIVE Control Center Frontend Index Not Found</h1>", status_code=404)
    return FileResponse(index_file)


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "REVIVE Autonomous Revenue Recovery",
        "engine_version": "0.4.0",
        "policy_version": "1.0.0",
        "executor_version": "1.0.0",
        "environment": "synthetic_simulation_benchmark"
    }


@app.get("/api/overview", response_model=SimulationSummaryResponse)
async def get_overview():
    return state.get_summary()


@app.post("/api/simulation/run", response_model=SimulationSummaryResponse)
async def run_simulation(req: SimulationRequest):
    return state.initialize_session(seed=req.seed, size=req.size, scenario=req.scenario)


@app.get("/api/recovery-cases", response_model=List[RecoveryCaseListItem])
async def list_recovery_cases(
    status: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None)
):
    return state.get_cases(status_filter=status, action_filter=action, search_query=search, sort_by=sort)


@app.get("/api/recovery-cases/{event_id}", response_model=RecoveryCaseDetailResponse)
async def get_recovery_case(event_id: str):
    detail = state.get_case_detail(event_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Recovery case '{event_id}' not found.")
    return detail


@app.post("/api/recovery-cases/{event_id}/execute", response_model=ExecuteRecoveryResponse)
async def execute_recovery_action(event_id: str):
    res = state.execute_recovery(event_id)
    if not res.success and "not found" in res.message.lower():
        raise HTTPException(status_code=404, detail=res.message)
    return res


@app.get("/api/safety", response_model=SafetyDashboardResponse)
async def get_safety_metrics():
    return state.get_safety_dashboard()


@app.get("/api/audit", response_model=List[AuditLogItem])
async def get_audit_trail(limit: int = Query(default=100, ge=1, le=1000)):
    return state.get_audit_events(limit=limit)


@app.get("/api/benchmark", response_model=BenchmarkResponse)
async def get_benchmark_comparison():
    return state.get_benchmark_report()
