"""Structured JSON logging configuration for the Flask backend."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

# LogRecord attributes that must not be copied into JSON output.
_BASE_LOGRECORD_ATTRS = frozenset(
    logging.LogRecord(
        name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None
    ).__dict__
)
_RESERVED_LOGRECORD_ATTRS = _BASE_LOGRECORD_ATTRS | frozenset({"message", "asctime", "taskName"})


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line with standard and extra fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }

        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id

        for key, value in record.__dict__.items():
            if key in _RESERVED_LOGRECORD_ATTRS or key in payload:
                continue
            if key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def setup_logging(log_level: str | None = None) -> logging.Logger:
    """Configure the application logger with JSON output to stdout.

    Args:
        log_level: Logging level name (e.g. INFO). Defaults to LOG_LEVEL env or INFO.

    Returns:
        Configured logger named ``app``.
    """
    level_name = (log_level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    logger = logging.getLogger("app")
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False

    # Request access logs are emitted by our after_request hook instead.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    return logger


def log_event(logger: logging.Logger, level: int, message: str, **fields) -> None:
    """Log a structured event, attaching the current request_id when available."""
    try:
        from flask import g

        request_id = getattr(g, "request_id", None)
    except RuntimeError:
        request_id = None

    extra = {"request_id": request_id, **fields}
    logger.log(level, message, extra=extra)
