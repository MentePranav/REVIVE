"""
FastAPI Application for the REVIVE Interactive Revenue Recovery Control Center.
Serves REST APIs with correlation ID tracing, structured error handling, and SPA frontend.
"""

from pathlib import Path
from typing import List, Optional
import uuid

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from core.config import APP_CONFIG
from core.environment_validator import EnvironmentValidator
from core.errors import ReviveError
from core.logging import get_logger
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

logger = get_logger("revive.server")

app = FastAPI(
    title=APP_CONFIG.application_name,
    version=APP_CONFIG.application_version,
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


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Assigns or propagates correlation IDs across the request lifecycle."""
    corr_id = request.headers.get("X-Correlation-ID") or f"req_{uuid.uuid4().hex[:12]}"
    request.state.correlation_id = corr_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = corr_id
    return response


@app.exception_handler(ReviveError)
async def revive_error_handler(request: Request, exc: ReviveError):
    """Global structured error handler for domain exceptions."""
    corr_id = getattr(request.state, "correlation_id", None)
    if not exc.correlation_id:
        exc.correlation_id = corr_id
    logger.warning(f"Handled ReviveError: {exc.message}", extra={"correlation_id": corr_id, "error_code": exc.error_code.value})
    status_code = 404 if "not found" in exc.message.lower() else 400
    return JSONResponse(status_code=status_code, content=exc.to_dict())


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Prevents stack trace leaks for unhandled server exceptions."""
    corr_id = getattr(request.state, "correlation_id", None)
    logger.error(f"Unhandled System Error: {str(exc)}", extra={"correlation_id": corr_id})
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "error_code": "SYSTEM_ERROR",
            "message": "An unexpected internal server error occurred. Please consult server logs.",
            "correlation_id": corr_id
        }
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
    is_valid, errors, details = EnvironmentValidator.validate()
    fingerprint = APP_CONFIG.compute_reproducibility_fingerprint(seed=state.seed, size=state.size)
    return {
        "status": "healthy" if is_valid else "degraded",
        "service": APP_CONFIG.application_name,
        "application_version": APP_CONFIG.application_version,
        "engine_version": APP_CONFIG.engine_version,
        "policy_version": APP_CONFIG.policy_version,
        "executor_version": APP_CONFIG.executor_version,
        "evaluation_version": APP_CONFIG.evaluation_version,
        "mode": APP_CONFIG.mode,
        "reproducibility_fingerprint": fingerprint,
        "environment_valid": is_valid,
        "environment_errors": errors
    }


@app.get("/api/overview", response_model=SimulationSummaryResponse)
async def get_overview():
    return state.get_summary()


@app.post("/api/simulation/run", response_model=SimulationSummaryResponse)
async def run_simulation(req: SimulationRequest):
    return state.initialize_session(seed=req.seed, size=req.size, scenario=req.scenario)


@app.post("/api/demo/reset", response_model=SimulationSummaryResponse)
async def reset_demo():
    """Resets the demo session to the deterministic default golden state."""
    return state.reset_demo_session()


@app.get("/api/recovery-cases", response_model=List[RecoveryCaseListItem])
async def list_recovery_cases(
    status: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None)
):
    return state.get_cases(status_filter=status, action_filter=action, search_query=search, sort_by=sort)


@app.get("/api/recovery-cases/{event_id}", response_model=RecoveryCaseDetailResponse)
async def get_recovery_case(event_id: str, request: Request):
    detail = state.get_case_detail(event_id)
    if not detail:
        corr_id = getattr(request.state, "correlation_id", None)
        raise ReviveError(f"Recovery case '{event_id}' not found.", correlation_id=corr_id)
    return detail


@app.post("/api/recovery-cases/{event_id}/execute", response_model=ExecuteRecoveryResponse)
async def execute_recovery_action(event_id: str, request: Request):
    corr_id = getattr(request.state, "correlation_id", None)
    res = state.execute_recovery(event_id, correlation_id=corr_id)
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
