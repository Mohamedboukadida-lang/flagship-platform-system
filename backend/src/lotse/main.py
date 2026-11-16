"""API entry point: `uvicorn lotse.main:create_app --factory`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lotse import __version__
from lotse.core import health, tracing
from lotse.core.errors import install_error_handlers
from lotse.core.middleware import RequestContextMiddleware
from lotse.core.resources import Resources
from lotse.modules.tenancy import api as tenancy_api
from lotse.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    prefix = settings.api_prefix
    resources = Resources(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await resources.start()
        try:
            yield
        finally:
            await resources.stop()

    app = FastAPI(
        title="Lotse API",
        version=__version__,
        lifespan=lifespan,
        docs_url=f"{prefix}/docs" if settings.env != "prod" else None,
        openapi_url=f"{prefix}/openapi.json",
        redoc_url=None,
    )
    app.state.resources = resources

    tracing.instrument(app, settings)
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)

    app.include_router(health.router)  # unprefixed: what the kubelet probes
    if prefix:
        app.include_router(health.router, prefix=prefix)  # reachable through the ingress
    app.include_router(tenancy_api.router, prefix=f"{prefix}/v1")
    return app
