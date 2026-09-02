"""
Centralized Application Configuration and Reproducibility Fingerprint for REVIVE.
Distinguishes Safe Configuration from Developer Settings and calculates deterministic hash digests.
"""

import hashlib
import json
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


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

    # Networking & Server
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"

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


# Singleton default app config
APP_CONFIG = ReviveAppConfig()
