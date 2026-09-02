"""
Structured JSON Logger and Sanitizer for REVIVE.
Ensures comprehensive observability with correlation IDs while strictly avoiding secrets/PII.
"""

from datetime import datetime, timezone
import json
import logging
import sys
from typing import Any, Dict, Optional

SENSITIVE_KEYS = {"api_key", "secret", "password", "token", "auth_token", "private_key", "credentials"}


def sanitize_payload(obj: Any) -> Any:
    """Recursively redacts any sensitive keys from log dictionaries."""
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            if any(s in k.lower() for s in SENSITIVE_KEYS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_payload(v)
        return sanitized
    elif isinstance(obj, list):
        return [sanitize_payload(item) for item in obj]
    return obj


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as single-line structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include custom attributes attached to the LogRecord
        if hasattr(record, "correlation_id") and record.correlation_id:
            log_entry["correlation_id"] = record.correlation_id
        if hasattr(record, "event") and record.event:
            log_entry["event"] = record.event
        if hasattr(record, "payment_id") and record.payment_id:
            log_entry["payment_id"] = record.payment_id
        if hasattr(record, "action") and record.action:
            log_entry["action"] = record.action
        if hasattr(record, "details") and record.details:
            log_entry["details"] = sanitize_payload(record.details)

        return json.dumps(log_entry)


def get_logger(name: str = "revive") -> logging.Logger:
    """Returns a configured structured logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    return logger
