"""
REVIVE Core Package: Reliability, Configuration, Logging, and Error Taxonomy.
"""

from core.config import APP_CONFIG, ReviveAppConfig
from core.environment_validator import EnvironmentValidator
from core.errors import (
    AuthorizationError,
    ErrorCategory,
    EvaluationError,
    ExecutionError,
    InputError,
    PolicyError,
    ReviveError,
    SimulationError,
    SystemError,
)
from core.logging import get_logger

__all__ = [
    "APP_CONFIG",
    "ReviveAppConfig",
    "EnvironmentValidator",
    "ReviveError",
    "InputError",
    "PolicyError",
    "AuthorizationError",
    "ExecutionError",
    "SimulationError",
    "EvaluationError",
    "SystemError",
    "ErrorCategory",
    "get_logger",
]
