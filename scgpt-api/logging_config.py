"""Structured logging for the scGPT API.

Two handlers are attached to the root logger:

* a console handler – useful for ``docker logs`` / ``kubectl logs``;
* a size-rotating file handler under ``logs/``.

Both emit JSON lines when ``logging.json`` is true in ``config.yaml``. The
JSON record always contains ``timestamp``, ``level``, ``logger`` and
``message`` plus any structured fields supplied through the standard
``extra={}`` mechanism. ``request_id`` is automatically injected from a
ContextVar so every log line emitted during a request can be correlated.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from config import LoggingConfig

# A ContextVar lets us thread the request id through async tasks without
# explicit plumbing. Middleware in app.py sets it for every incoming request.
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


# Standard LogRecord attributes – everything else we treat as structured
# user data and merge into the JSON payload.
_RESERVED_RECORD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
}


class JsonFormatter(logging.Formatter):
    """Render log records as a single JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid

        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_ATTRS or key.startswith("_"):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Human-friendly formatter for local development."""

    _FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"

    def __init__(self) -> None:
        super().__init__(self._FORMAT, datefmt="%Y-%m-%dT%H:%M:%S%z")

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        rid = request_id_var.get()
        return f"{base} | request_id={rid}" if rid else base


def configure_logging(cfg: LoggingConfig) -> None:
    """Idempotently configure the root logger.

    Safe to call more than once (e.g. on Uvicorn reload) – handlers are
    cleared before re-attaching.
    """
    Path(cfg.file).parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(cfg.level)

    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter: logging.Formatter = JsonFormatter() if cfg.json_format else TextFormatter()

    console = logging.StreamHandler(stream=sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        filename=cfg.file,
        maxBytes=cfg.max_bytes,
        backupCount=cfg.backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Tame the noisy libraries; they will still emit warnings and errors.
    for noisy in ("uvicorn.access", "matplotlib", "PIL", "numba", "h5py"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
