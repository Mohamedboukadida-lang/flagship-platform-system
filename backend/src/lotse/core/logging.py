"""JSON log lines on stdout (spec section 13): ids and counts, never request content.

Configured by the server, not by the app: uvicorn loads backend/logging.json, which uses
JsonFormatter below. Tests therefore keep pytest's own log capture.
"""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from lotse.core.tracing import current_trace_id

request_id_var: ContextVar[str | None] = ContextVar("lotse_request_id", default=None)

# Attributes every LogRecord has; anything else on a record came from `extra=`.
# uvicorn adds `color_message`, a copy of the message with terminal colour codes.
_STANDARD = frozenset(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
    "taskName",
    "color_message",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if (request_id := request_id_var.get()) is not None:
            line["request_id"] = request_id
        if (trace_id := current_trace_id()) is not None:
            line["trace_id"] = trace_id
        for key, value in record.__dict__.items():
            if key not in _STANDARD and not key.startswith("_"):
                line[key] = value
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str)
