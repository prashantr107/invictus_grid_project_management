"""Structured application logging (TRD §14).

Every application logger lives under the ``app`` namespace and emits one JSON
object per event with severity, UTC timestamp, message, and, when in a request
context, the request ID and actor ID. `RequestContextMiddleware` adds route,
status and duration to the per-request access event.
"""

import json
import logging
import sys
from datetime import datetime, timezone

from app.core.config import get_settings

_EXTRA_FIELDS = (
    "request_id",
    "actor_id",
    "method",
    "path",
    "status",
    "duration_ms",
    "code",
    "event",
)


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON, including known structured fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging() -> None:
    """Attach the JSON handler to the ``app`` logger tree once."""
    logger = logging.getLogger("app")
    if any(isinstance(handler.formatter, JsonFormatter) for handler in logger.handlers):
        return
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(get_settings().log_level.upper())
    logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
