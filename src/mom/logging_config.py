"""Structured logging setup for production."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key in ("model_id", "graph", "request_id", "duration_ms", "route"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, default=str)


def setup_logging(*, level: str = "INFO", json_logs: bool = False, stream: Any = None) -> None:
    """Idempotent root logging for the mom process."""
    root = logging.getLogger()
    # Avoid duplicate handlers on reload
    if getattr(root, "_mom_configured", False):
        root.setLevel(level.upper())
        return
    handler = logging.StreamHandler(stream or sys.stdout)
    if json_logs:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    setattr(root, "_mom_configured", True)


def get_logger(name: str = "mom") -> logging.Logger:
    return logging.getLogger(name)
