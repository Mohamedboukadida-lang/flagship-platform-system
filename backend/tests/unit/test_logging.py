import json
import logging
import sys

import pytest

from lotse.core.logging import JsonFormatter, request_id_var


def record(message: str = "hello %s", *args: object, **extra: object) -> logging.LogRecord:
    rec = logging.makeLogRecord(
        {
            "name": "lotse.test",
            "levelno": 20,
            "levelname": "INFO",
            "msg": message,
            "args": args or ("world",),
        }
    )
    rec.__dict__.update(extra)
    return rec


def test_line_is_json_with_the_base_fields() -> None:
    line = json.loads(JsonFormatter().format(record()))
    assert line["message"] == "hello world"
    assert line["level"] == "info"
    assert line["logger"] == "lotse.test"
    assert line["time"].endswith("+00:00")
    assert "request_id" not in line
    assert "trace_id" not in line


def test_extra_fields_and_request_id_are_included() -> None:
    token = request_id_var.set("req-12345678")
    try:
        line = json.loads(JsonFormatter().format(record(status=201, tenant_id="t-1")))
    finally:
        request_id_var.reset(token)
    assert line["request_id"] == "req-12345678"
    assert line["status"] == 201
    assert line["tenant_id"] == "t-1"


def test_uvicorn_colour_copy_is_dropped() -> None:
    line = json.loads(JsonFormatter().format(record(color_message="\x1b[36mhello\x1b[0m")))
    assert "color_message" not in line


def test_exception_is_rendered() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        rec = record(exc_info=sys.exc_info())
    line = json.loads(JsonFormatter().format(rec))
    assert "ValueError: boom" in line["exception"]


def test_values_that_are_not_json_still_serialise() -> None:
    line = json.loads(JsonFormatter().format(record(when=object())))
    assert line["when"].startswith("<object object")


@pytest.mark.parametrize("name", ["uvicorn", "uvicorn.error"])
def test_logging_config_routes_uvicorn_through_the_json_handler(name: str) -> None:
    from pathlib import Path

    config = json.loads((Path(__file__).resolve().parents[2] / "logging.json").read_text())
    assert config["formatters"]["json"]["()"] == "lotse.core.logging.JsonFormatter"
    assert config["loggers"][name]["propagate"] is True
    assert config["loggers"]["uvicorn.access"]["propagate"] is False  # we log our own line
