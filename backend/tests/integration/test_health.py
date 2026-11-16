import httpx
from fastapi import FastAPI

from lotse.main import create_app

from ..conftest import Jwks, make_settings


async def _get(app: FastAPI, path: str) -> httpx.Response:
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http,
    ):
        return await http.get(path)


async def test_ready_when_every_store_answers(client: httpx.AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_not_ready_when_postgres_is_unreachable(jwks: Jwks, database: str) -> None:
    dead = "postgresql+asyncpg://lotse_app:irrelevant@127.0.0.1:1/lotse_test"
    response = await _get(create_app(make_settings(jwks, database_url=dead)), "/readyz")
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["failed"] == ["database"]
    assert "irrelevant" not in response.text


async def test_not_ready_when_redis_is_unreachable(jwks: Jwks, database: str) -> None:
    app = create_app(make_settings(jwks, redis_url="redis://127.0.0.1:1/0"))
    response = await _get(app, "/readyz")
    assert response.status_code == 503
    assert response.json()["failed"] == ["redis"]


async def test_liveness_does_not_depend_on_stores(jwks: Jwks, database: str) -> None:
    app = create_app(make_settings(jwks, redis_url="redis://127.0.0.1:1/0"))
    assert (await _get(app, "/healthz")).status_code == 200
