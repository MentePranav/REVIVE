"""
Centralized Application Configuration and Reproducibility Fingerprint for REVIVE.
Distinguishes Safe Configuration from Developer Settings and calculates deterministic hash digests.
"""

import hashlib
import json
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def _get_env_allowed_origins() -> List[str]:
    raw = os.getenv("APP_ALLOWED_ORIGINS", os.getenv("ALLOWED_ORIGINS", ""))
    if not raw.strip():
        return ["*"]
    if raw.strip().startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return [o.strip() for o in raw.split(",") if o.strip()]


def _get_env_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is not None and val.strip():
        try:
            return int(val.strip())
        except ValueError:
            pass
    return default


def _get_env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is not None and val.strip():
        return val.strip().lower() in ("true", "1", "yes")
    return default


class ReviveAppConfig(BaseModel):
    """Centralized configuration for the REVIVE ecosystem."""

    # Application Metadata
    application_name: str = "REVIVE — Autonomous Revenue Recovery"
    application_version: str = "1.0.0"
    engine_version: str = "0.4.0"
    policy_version: str = "1.0.0"
    executor_version: str = "1.0.0"
    evaluation_version: str = "1.0.0"
    mode: str = "synthetic_simulation_benchmark"

    # Default Demo Parameters
    default_demo_seed: int = Field(default=42, ge=1)
    default_demo_size: int = Field(default=100, ge=10, le=10000)
    default_scenario: str = "balanced"

    # Networking & Server (Configurable via PORT, HOST, ALLOWED_ORIGINS, etc.)
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)
    log_level: str = "INFO"
    allowed_origins: List[str] = Field(default=["*"])
    rate_limit_enabled: bool = True
    security_headers_enabled: bool = True

    # Safety Guard: Prohibit disabling policy via configuration
    allow_policy_bypass: bool = False

    def compute_reproducibility_fingerprint(self, seed: Optional[int] = None, size: Optional[int] = None) -> str:
        """
        Computes an invariant SHA-256 fingerprint over configuration, versions, and seeds.
        Guarantees that identical parameters produce identical fingerprints.
        """
        s = seed if seed is not None else self.default_demo_seed
        sz = size if size is not None else self.default_demo_size

        payload = {
            "application_version": self.application_version,
            "engine_version": self.engine_version,
            "policy_version": self.policy_version,
            "executor_version": self.executor_version,
            "evaluation_version": self.evaluation_version,
            "seed": s,
            "size": sz,
            "mode": self.mode,
        }
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def create_app_config() -> ReviveAppConfig:
    """Instantiates ReviveAppConfig populated from safe environment variables with fallback defaults."""
    env_port = _get_env_int("PORT", _get_env_int("APP_PORT", 8000))
    default_host = "0.0.0.0" if "PORT" in os.environ else "127.0.0.1"
    env_host = os.getenv("HOST", os.getenv("APP_HOST", default_host))
    env_log = os.getenv("LOG_LEVEL", "INFO")
    env_origins = _get_env_allowed_origins()
    env_rate_limit = _get_env_bool("APP_RATE_LIMIT_ENABLED", _get_env_bool("RATE_LIMIT_ENABLED", True))
    env_sec_headers = _get_env_bool("APP_SECURITY_HEADERS_ENABLED", _get_env_bool("SECURITY_HEADERS_ENABLED", True))

    return ReviveAppConfig(
        host=env_host,
        port=env_port,
        log_level=env_log,
        allowed_origins=env_origins,
        rate_limit_enabled=env_rate_limit,
        security_headers_enabled=env_sec_headers,
        allow_policy_bypass=False
    )


# Singleton default app config
APP_CONFIG = create_app_config()
