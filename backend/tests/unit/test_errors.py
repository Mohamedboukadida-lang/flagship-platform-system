import httpx
import pytest
from fastapi import FastAPI

from lotse.core.errors import Forbidden, Unauthorized, install_error_handlers


@pytest.fixture
def http() -> httpx.AsyncClient:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/forbidden")
    async def forbidden() -> None:
        raise Forbidden("internal: user 42 lacks role on tenant 7")

    @app.get("/unauthorized")
    async def unauthorized() -> None:
        raise Unauthorized("internal: signature mismatch")

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("internal: password=hunter2")

    @app.get("/items/{number}")
    async def item(number: int) -> int:
        return number

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_app_error_is_problem_json_without_the_internal_detail(
    http: httpx.AsyncClient,
) -> None:
    response = await http.get("/forbidden")
    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body == {
        "type": "https://lotse.example/errors/forbidden",
        "title": "Not allowed",
        "status": 403,
        "detail": "Not allowed",
        "code": "forbidden",
        "trace_id": None,
    }
    assert "internal" not in response.text


async def test_unauthorized_carries_the_challenge_header(http: httpx.AsyncClient) -> None:
    response = await http.get("/unauthorized")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert "signature" not in response.text


async def test_unhandled_exception_is_a_generic_500(http: httpx.AsyncClient) -> None:
    response = await http.get("/boom")
    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "internal_error"
    assert "hunter2" not in response.text


async def test_unknown_path_is_problem_json(http: httpx.AsyncClient) -> None:
    response = await http.get("/nope")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "not_found"


async def test_validation_error_does_not_echo_the_input(http: httpx.AsyncClient) -> None:
    response = await http.get("/items/secret-value")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["errors"][0]["loc"] == ["path", "number"]
    assert "secret-value" not in response.text
