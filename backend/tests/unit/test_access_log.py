"""One access line per request, with ids and timings and never request content."""

import json

import httpx
import pytest

from lotse.core.logging import JsonFormatter
from lotse.main import create_app

from ..conftest import Jwks, make_settings


def access_lines(caplog: pytest.LogCaptureFixture) -> list:
    return [r for r in caplog.records if r.name == "lotse.access"]


@pytest.fixture
def http(jwks: Jwks) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=create_app(make_settings(jwks)), raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_one_line_with_path_status_ids_and_duration(
    http: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="lotse.access")
    response = await http.get("/v1/me", headers={"X-Request-ID": "client-id-12345"})
    [line] = access_lines(caplog)
    assert line.method == "GET"
    assert line.path == "/v1/me"
    assert line.status == response.status_code == 401
    assert line.duration_ms >= 0
    assert line.tenant_id is None

    # The line carries the trace id the client sees in the problem body, even when it is
    # formatted after the request has ended (as here).
    rendered = json.loads(JsonFormatter().format(line))
    assert rendered["trace_id"] == response.json()["trace_id"]
    assert rendered["request_id"] == response.headers["x-request-id"] == "client-id-12345"


async def test_long_paths_are_truncated(
    http: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="lotse.access")
    await http.get("/" + "x" * 500)
    [line] = access_lines(caplog)
    assert line.status == 404
    assert len(line.path) == 200


async def test_successful_probes_are_not_logged(
    http: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="lotse.access")
    assert (await http.get("/healthz")).status_code == 200
    assert access_lines(caplog) == []
