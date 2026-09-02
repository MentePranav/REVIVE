"""
Standardized Error Taxonomy for the REVIVE Autonomous Revenue Recovery System.
Provides structured, machine-readable error categories without leaking internal stack traces.
"""

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCategory(str, Enum):
    INPUT_ERROR = "INPUT_ERROR"
    POLICY_ERROR = "POLICY_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    SIMULATION_ERROR = "SIMULATION_ERROR"
    EVALUATION_ERROR = "EVALUATION_ERROR"
    SYSTEM_ERROR = "SYSTEM_ERROR"


class ReviveError(Exception):
    """Base exception for all structured errors in REVIVE."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCategory = ErrorCategory.SYSTEM_ERROR,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.correlation_id = correlation_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": True,
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "correlation_id": self.correlation_id,
        }


class InputError(ReviveError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, correlation_id: Optional[str] = None):
        super().__init__(message, ErrorCategory.INPUT_ERROR, details, correlation_id)


class PolicyError(ReviveError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, correlation_id: Optional[str] = None):
        super().__init__(message, ErrorCategory.POLICY_ERROR, details, correlation_id)


class AuthorizationError(ReviveError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, correlation_id: Optional[str] = None):
        super().__init__(message, ErrorCategory.AUTHORIZATION_ERROR, details, correlation_id)


class ExecutionError(ReviveError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, correlation_id: Optional[str] = None):
        super().__init__(message, ErrorCategory.EXECUTION_ERROR, details, correlation_id)


class SimulationError(ReviveError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, correlation_id: Optional[str] = None):
        super().__init__(message, ErrorCategory.SIMULATION_ERROR, details, correlation_id)


class EvaluationError(ReviveError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, correlation_id: Optional[str] = None):
        super().__init__(message, ErrorCategory.EVALUATION_ERROR, details, correlation_id)


class SystemError(ReviveError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, correlation_id: Optional[str] = None):
        super().__init__(message, ErrorCategory.SYSTEM_ERROR, details, correlation_id)
