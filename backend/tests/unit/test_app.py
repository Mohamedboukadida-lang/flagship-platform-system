"""The assembled app, without its lifespan: only paths that need no store."""

import re
from typing import Any

import httpx

from lotse.main import create_app

from ..conftest import Jwks, make_settings


def http(jwks: Jwks, **settings: Any) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=create_app(make_settings(jwks, **settings)))
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_healthz_and_request_id(jwks: Jwks) -> None:
    response = await http(jwks).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert re.fullmatch(r"[0-9a-f-]{36}", response.headers["x-request-id"])


async def test_wellformed_request_id_is_kept_and_malformed_replaced(jwks: Jwks) -> None:
    client = http(jwks)
    kept = await client.get("/healthz", headers={"X-Request-ID": "client-id-12345"})
    assert kept.headers["x-request-id"] == "client-id-12345"
    replaced = await client.get("/healthz", headers={"X-Request-ID": "bad id with spaces"})
    assert replaced.headers["x-request-id"] != "bad id with spaces"


async def test_anonymous_request_is_401_with_a_trace_id(jwks: Jwks) -> None:
    response = await http(jwks).get("/v1/me")
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert re.fullmatch(r"[0-9a-f]{32}", response.json()["trace_id"])


async def test_api_prefix_moves_the_api_and_keeps_the_probe_path(jwks: Jwks) -> None:
    """Behind the ingress the API lives under /api; the kubelet still probes /healthz."""
    client = http(jwks, api_prefix="/api")
    assert (await client.get("/api/v1/me")).status_code == 401
    assert (await client.get("/v1/me")).status_code == 404
    assert (await client.get("/healthz")).status_code == 200
    assert (await client.get("/api/healthz")).status_code == 200
    assert (await client.get("/api/openapi.json")).status_code == 200


async def test_docs_are_off_in_prod(jwks: Jwks) -> None:
    assert (await http(jwks, env="dev").get("/docs")).status_code == 200
    assert (await http(jwks, env="prod").get("/docs")).status_code == 404
