"""
Lightweight In-Process Sliding-Window Rate Limiter for REVIVE.
Provides burst and abuse protection for public synthetic evaluation demo endpoints.
"""

from collections import defaultdict
from datetime import datetime, timezone
import threading
import time
from typing import Dict, List, Optional, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class InMemoryRateLimiter:
    """
    Thread-safe in-memory sliding-window rate limiter.
    Maintains a rolling window of request timestamps per client IP.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._requests: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        self._last_cleanup = time.time()

        # Route-specific rate limits: (max_requests, window_seconds)
        self.limits: Dict[str, Tuple[int, int]] = {
            "/api/simulation/run": (30, 60),          # 30 simulation runs per minute
            "/api/demo/reset": (30, 60),              # 30 resets per minute
            "/api/recovery-cases/execute": (60, 60),  # 60 executions per minute
            "default_api": (300, 60),                 # 300 general API requests per minute
        }

    def _get_route_key(self, path: str) -> str:
        if path.startswith("/api/simulation/run"):
            return "/api/simulation/run"
        if path.startswith("/api/demo/reset"):
            return "/api/demo/reset"
        if "/execute" in path and path.startswith("/api/recovery-cases/"):
            return "/api/recovery-cases/execute"
        if path.startswith("/api/"):
            return "default_api"
        return "non_api"

    def _cleanup_old_records(self, now: float):
        """Purge records older than 120 seconds to prevent memory growth."""
        if now - self._last_cleanup < 60:
            return
        self._last_cleanup = now
        expired_cutoff = now - 120
        for client_ip in list(self._requests.keys()):
            for route_key in list(self._requests[client_ip].keys()):
                self._requests[client_ip][route_key] = [
                    t for t in self._requests[client_ip][route_key] if t > expired_cutoff
                ]
                if not self._requests[client_ip][route_key]:
                    del self._requests[client_ip][route_key]
            if not self._requests[client_ip]:
                del self._requests[client_ip]

    def check_rate_limit(self, client_ip: str, path: str) -> Tuple[bool, Optional[int]]:
        """
        Checks whether the given client IP has exceeded rate limits for the path.
        Returns (is_allowed, retry_after_seconds).
        """
        route_key = self._get_route_key(path)
        if route_key == "non_api":
            return True, None

        max_reqs, window_sec = self.limits.get(route_key, self.limits["default_api"])
        now = time.time()
        window_start = now - window_sec

        with self._lock:
            self._cleanup_old_records(now)
            timestamps = self._requests[client_ip][route_key]
            # Filter timestamps within the current window
            valid_timestamps = [t for t in timestamps if t > window_start]
            self._requests[client_ip][route_key] = valid_timestamps

            if len(valid_timestamps) >= max_reqs:
                oldest = valid_timestamps[0]
                retry_after = max(1, int(window_sec - (now - oldest)))
                return False, retry_after

            valid_timestamps.append(now)
            return True, None

    def reset(self):
        """Resets all recorded rate limit buckets (useful for test isolation)."""
        with self._lock:
            self._requests.clear()


# Global rate limiter instance
RATE_LIMITER = InMemoryRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI Middleware enforcing sliding-window rate limiting on API endpoints."""

    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        # Only apply rate limiting to /api routes
        if request.url.path.startswith("/api/"):
            client_ip = request.client.host if request.client else "127.0.0.1"
            # Respect forward headers only if present
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                client_ip = forwarded.split(",")[0].strip()

            is_allowed, retry_after = RATE_LIMITER.check_rate_limit(client_ip, request.url.path)
            if not is_allowed:
                corr_id = getattr(request.state, "correlation_id", "req_rate_limit")
                response = JSONResponse(
                    status_code=429,
                    content={
                        "error": True,
                        "error_code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded. Please wait {retry_after} seconds before retrying.",
                        "retry_after": retry_after,
                        "correlation_id": corr_id
                    }
                )
                response.headers["Retry-After"] = str(retry_after)
                return response

        return await call_next(request)
