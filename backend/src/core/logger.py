"""Structured logging for Nexis.

Two levels:
  - PRODUCTION (INFO): key steps, state transitions, request summaries
  - DEBUG: verbose internals, payloads, timing

Toggle via LOG_LEVEL env var (default: INFO, set to DEBUG for verbose).
"""

import logging
import sys
from functools import lru_cache

import os


@lru_cache(maxsize=1)
def _get_log_level() -> int:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level, logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Create a logger with consistent formatting."""
    logger = logging.getLogger(f"nexis.{name}")

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        fmt = logging.Formatter(
            "%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)

    logger.setLevel(_get_log_level())
    return logger
