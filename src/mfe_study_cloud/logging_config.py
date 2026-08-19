"""Allowlisted JSON logs that exclude secrets and document content."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

ALLOWED_EXTRA_FIELDS = {
    "concurrency",
    "document_id",
    "job_id",
    "provider",
    "request_id",
    "status",
    "tenant_id",
    "worker_id",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for field in ALLOWED_EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None and isinstance(value, str | int | float | bool):
                payload[field] = value
        if record.exc_info and record.exc_info[0] is not None:
            payload["error_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
