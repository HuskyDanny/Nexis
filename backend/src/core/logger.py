"""Structured logging for Nexis.

Two levels:
  - PRODUCTION (INFO): key steps, state transitions, request summaries
  - DEBUG: verbose internals, payloads, timing

Toggle via LOG_LEVEL env var (default: INFO, set to DEBUG for verbose).
Set LOG_FORMAT=json for JSON structured output (production); default is text.
"""

import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from functools import lru_cache

import os


@lru_cache(maxsize=1)
def _get_log_level() -> int:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level, logging.INFO)


@lru_cache(maxsize=1)
def _get_log_format() -> str:
    """Return 'json' or 'text'. Reads settings.log_format if available, else env var."""
    try:
        from src.core.config import settings

        return getattr(settings, "log_format", os.environ.get("LOG_FORMAT", "text"))
    except Exception:
        return os.environ.get("LOG_FORMAT", "text")


class JSONFormatter(logging.Formatter):
    """Outputs one JSON object per log line for structured log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Propagate request_id if attached to the record
        request_id = getattr(record, "request_id", None)
        if request_id:
            entry["request_id"] = request_id

        if record.exc_info and record.exc_info[1] is not None:
            entry["exception"] = "".join(traceback.format_exception(*record.exc_info))

        return json.dumps(entry, ensure_ascii=False)


_TEXT_FORMATTER = logging.Formatter(
    "%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)


def _make_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    if _get_log_format() == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(_TEXT_FORMATTER)
    return handler


def get_logger(name: str) -> logging.Logger:
    """Create a logger with consistent formatting."""
    logger = logging.getLogger(f"nexis.{name}")

    if not logger.handlers:
        logger.addHandler(_make_handler())

    logger.setLevel(_get_log_level())
    return logger
