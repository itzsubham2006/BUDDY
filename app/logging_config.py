"""
Structured logging setup for Jarvis.

Guarantees:
* Logs go to both console and a rotating file under `data/logs`.
* A `SensitiveDataFilter` scrubs common secret patterns before they hit
  any handler, as defense-in-depth (callers should still avoid logging
  secrets directly).
"""

from __future__ import annotations

import logging
import logging.handlers
import re
from pathlib import Path

from app.config import Settings

_SENSITIVE_PATTERNS = [
    re.compile(r"(api[_-]?key\s*[:=]\s*)([^\s,\"']+)", re.IGNORECASE),
    re.compile(r"(authorization:\s*bearer\s+)([^\s,\"']+)", re.IGNORECASE),
    re.compile(r"(password\s*[:=]\s*)([^\s,\"']+)", re.IGNORECASE),
    re.compile(r"(token\s*[:=]\s*)([^\s,\"']+)", re.IGNORECASE),
]


class SensitiveDataFilter(logging.Filter):
    """Redacts substrings that look like secrets from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        redacted = msg
        for pattern in _SENSITIVE_PATTERNS:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True


def configure_logging(settings: Settings) -> logging.Logger:
    """Configure root logging for the application and return the app logger."""
    log_dir: Path = settings.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sensitive_filter = SensitiveDataFilter()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sensitive_filter)
    root_logger.addHandler(console_handler)

    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_dir / "jarvis.log"),
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(sensitive_filter)
    root_logger.addHandler(file_handler)

    app_logger = logging.getLogger("jarvis")
    app_logger.info("Logging configured (level=%s, dir=%s)", settings.log_level, log_dir)
    return app_logger
