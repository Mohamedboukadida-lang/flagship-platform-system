"""Liveness and readiness. Readiness checks every store the API needs to serve a request."""

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from lotse.core import db
from lotse.core.errors import problem
from lotse.core.resources import Resources

log = logging.getLogger(__name__)
router = APIRouter()

CHECK_TIMEOUT_SECONDS = 2.0


@router.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


async def _redis_ping(resources: Resources) -> None:
    await resources.redis.ping()


@router.get("/readyz", include_in_schema=False)
async def readyz(request: Request) -> JSONResponse:
    resources: Resources = request.app.state.resources
    checks = {
        "database": db.ping(resources.engine),
        "platform_database": resources.platform_db.ping(),
        "redis": _redis_ping(resources),
    }
    results = await asyncio.gather(
        *(asyncio.wait_for(check, CHECK_TIMEOUT_SECONDS) for check in checks.values()),
        return_exceptions=True,
    )
    failed = sorted(
        name
        for name, result in zip(checks, results, strict=True)
        if isinstance(result, BaseException)
    )
    if failed:
        log.warning("not_ready failed=%s", failed)
        # Names only: connection errors can carry hostnames and credentials.
        return problem(
            503, "not_ready", "Service not ready", "Service not ready", extra={"failed": failed}
        )
    return JSONResponse({"status": "ready"})
