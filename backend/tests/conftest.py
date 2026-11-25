"""Shared fixtures.

Unit tests need no services. Integration and isolation tests need Postgres and Redis
(`make up`); they build a throwaway database `lotse_test` and never touch `lotse`.
"""

import asyncio
import json
import os
import threading
import time
from collections.abc import AsyncIterator, Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI

from lotse.core.ids import new_id
from lotse.main import create_app
from lotse.settings import Settings

BACKEND = Path(__file__).resolve().parents[1]

PG_HOST = os.environ.get("LOTSE_TEST_PG_HOST", "127.0.0.1:5432")
ADMIN_PASSWORD = os.environ.get("LOTSE_TEST_ADMIN_PASSWORD", "postgres_dev")
APP_PASSWORD = os.environ.get("LOTSE_TEST_APP_PASSWORD", "lotse_app_dev")
PLATFORM_PASSWORD = os.environ.get("LOTSE_TEST_PLATFORM_PASSWORD", "lotse_platform_dev")
REDIS_URL = os.environ.get("LOTSE_TEST_REDIS_URL", "redis://127.0.0.1:6379/15")
S3_URL = os.environ.get("LOTSE_TEST_S3_URL", "http://127.0.0.1:9000")
S3_ACCESS_KEY = os.environ.get("LOTSE_TEST_S3_ACCESS_KEY", "lotse_s3_dev")
S3_SECRET_KEY = os.environ.get("LOTSE_TEST_S3_SECRET_KEY", "lotse_s3_dev_secret")
S3_BUCKET = "lotse-test"
TEST_DB = "lotse_test"

ISSUER = "http://issuer.test/realms/lotse"
AUDIENCE = "lotse-api"


def dsn(user: str, password: str, database: str, driver: str = "postgresql") -> str:
    return f"{driver}://{user}:{password}@{PG_HOST}/{database}"


class Jwks:
    """A local identity provider: one RSA key, its JWKS over HTTP, and a token factory."""

    def __init__(self) -> None:
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = "test-key"
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        jwk.update(kid=self.kid, use="sig", alg="RS256")
        document = json.dumps({"keys": [jwk]}).encode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(document)

            def log_message(self, *args: Any) -> None:
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/certs"

    def token(
        self, sub: str = "sub-1", *, key: Any = None, alg: str = "RS256", **claims: Any
    ) -> str:
        """A valid token by default. Pass a claim as None to drop it."""
        now = int(time.time())
        payload: dict[str, Any] = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": sub,
            "iat": now,
            "exp": now + 300,
            "email": f"{sub}@example.test",
            "name": f"Name of {sub}",
        }
        payload.update(claims)
        payload = {k: v for k, v in payload.items() if v is not None}
        return jwt.encode(payload, key or self.key, algorithm=alg, headers={"kid": self.kid})


@pytest.fixture(scope="session")
def jwks() -> Iterator[Jwks]:
    provider = Jwks()
    yield provider
    provider.server.shutdown()


@pytest.fixture(scope="session")
def database() -> Iterator[str]:
    """Fresh `lotse_test` with all migrations applied. Login roles are created if missing
    and otherwise left alone, so running the tests never changes a developer's passwords."""

    async def prepare() -> None:
        conn = await asyncpg.connect(dsn("postgres", ADMIN_PASSWORD, "postgres"))
        try:
            for role, password in (
                ("lotse_app", APP_PASSWORD),
                ("lotse_platform", PLATFORM_PASSWORD),
            ):
                if not await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", role):
                    await conn.execute(
                        f"CREATE ROLE {role} LOGIN NOBYPASSRLS PASSWORD '{password}'"
                    )
            await conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
            await conn.execute(f"CREATE DATABASE {TEST_DB}")
        finally:
            await conn.close()

    asyncio.run(prepare())
    patch = pytest.MonkeyPatch()
    patch.setenv(
        "LOTSE_MIGRATIONS_DATABASE_URL",
        dsn("postgres", ADMIN_PASSWORD, TEST_DB, "postgresql+asyncpg"),
    )
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    yield TEST_DB
    patch.undo()


@pytest.fixture
async def admin(database: str) -> AsyncIterator[asyncpg.Connection]:
    """Superuser connection for arranging data. Tables are emptied after each test."""
    conn = await asyncpg.connect(dsn("postgres", ADMIN_PASSWORD, database))
    yield conn
    await conn.execute("TRUNCATE memberships, users, tenants")
    await conn.close()


def make_settings(jwks: Jwks, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "env": "test",
        "database_url": dsn("lotse_app", APP_PASSWORD, TEST_DB, "postgresql+asyncpg"),
        "platform_database_url": dsn("lotse_platform", PLATFORM_PASSWORD, TEST_DB),
        "redis_url": REDIS_URL,
        "s3_bucket": S3_BUCKET,
        "s3_endpoint_url": S3_URL,
        "s3_access_key_id": S3_ACCESS_KEY,
        "s3_secret_access_key": S3_SECRET_KEY,
        "oidc_issuer": ISSUER,
        "oidc_jwks_url": jwks.url,
        "oidc_audience": AUDIENCE,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
def settings(jwks: Jwks) -> Settings:
    return make_settings(jwks)


@pytest.fixture
async def app(settings: Settings, admin: asyncpg.Connection) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


class World:
    """Two tenants that look alike: A has alice (admin) and adam (member), B has bob (admin)."""

    def __init__(self) -> None:
        self.tenant_a, self.tenant_b = new_id(), new_id()
        self.alice, self.adam, self.bob = new_id(), new_id(), new_id()


@pytest.fixture
async def world(admin: asyncpg.Connection) -> World:
    w = World()
    await admin.executemany(
        "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3)",
        [(w.tenant_a, "Tenant", "tenant-a"), (w.tenant_b, "Tenant", "tenant-b")],
    )
    await admin.executemany(
        "INSERT INTO users (id, oidc_sub, email, display_name) VALUES ($1, $2, $3, $4)",
        [
            (w.alice, "sub-alice", "alice@example.test", "Alice"),
            (w.adam, "sub-adam", "adam@example.test", "Adam"),
            (w.bob, "sub-bob", "bob@example.test", "Bob"),
        ],
    )
    await admin.executemany(
        "INSERT INTO memberships (tenant_id, user_id, role) VALUES ($1, $2, $3)",
        [
            (w.tenant_a, w.alice, "admin"),
            (w.tenant_a, w.adam, "member"),
            (w.tenant_b, w.bob, "admin"),
        ],
    )
    return w
