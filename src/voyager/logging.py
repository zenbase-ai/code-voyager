"""Structured logging for Voyager hook scripts.

Provides consistent stderr logging that keeps stdout clean for hook
responses. Designed for minimal noise by default (WARNING level).
"""

from __future__ import annotations

import logging
import os
import sys

# Cache configured loggers
_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger for hook scripts.

    Logs to stderr with format: [voyager:{name}] {level}: {message}
    Default level is WARNING; override with VOYAGER_LOG_LEVEL env var.

    Args:
        name: Logger name (typically the script/module name).

    Returns:
        Configured logger instance.
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(f"voyager.{name}")

    # Only configure if not already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(f"[voyager:{name}] %(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Set level from env var or default to WARNING
        level_name = os.environ.get("VOYAGER_LOG_LEVEL", "WARNING").upper()
        level = getattr(logging, level_name, logging.WARNING)
        logger.setLevel(level)

    _loggers[name] = logger
    return logger
