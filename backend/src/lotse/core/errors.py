"""Typed errors and their application/problem+json mapping (spec section 7)."""

import logging
from http import HTTPStatus
from typing import Any, ClassVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from lotse.core import tracing

log = logging.getLogger(__name__)

PROBLEM_JSON = "application/problem+json"
ERROR_TYPE_BASE = "https://lotse.example/errors/"


class AppError(Exception):
    status: ClassVar[int] = 500
    code: ClassVar[str] = "internal_error"
    title: ClassVar[str] = "Internal error"
    headers: ClassVar[dict[str, str] | None] = None

    def __init__(self, detail: str = "", *, public_detail: str | None = None) -> None:
        """`detail` is for logs; only `public_detail` (default: the title) reaches the client."""
        super().__init__(detail)
        self.public_detail = public_detail if public_detail is not None else self.title


class BadRequest(AppError):
    status, code, title = 400, "bad_request", "Bad request"


class Unauthorized(AppError):
    status, code, title = 401, "unauthorized", "Authentication required"
    headers: ClassVar[dict[str, str] | None] = {"WWW-Authenticate": "Bearer"}


class Forbidden(AppError):
    status, code, title = 403, "forbidden", "Not allowed"


class NotFound(AppError):
    status, code, title = 404, "not_found", "Not found"


class Conflict(AppError):
    status, code, title = 409, "conflict", "Conflict"


class GuardrailViolation(AppError):
    status, code, title = 422, "guardrail_violation", "Request blocked"


class RateLimited(AppError):
    status, code, title = 429, "rate_limited", "Too many requests"


class BudgetExceeded(AppError):
    status, code, title = 429, "budget_exceeded", "Budget exhausted"


class ProviderError(AppError):
    status, code, title = 502, "provider_error", "Model provider failed"


class ValidationFailed(AppError):
    status, code, title = 502, "model_output_invalid", "Model output invalid"


def problem(
    status: int,
    code: str,
    title: str,
    detail: str,
    *,
    headers: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"{ERROR_TYPE_BASE}{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "trace_id": tracing.current_trace_id(),
    }
    if extra:
        body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


_HTTP_CODES = {404: "not_found", 405: "method_not_allowed"}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status >= 500:
            log.error("app_error code=%s detail=%s", exc.code, exc)
        return problem(exc.status, exc.code, exc.title, exc.public_detail, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Location, message and type only: never echo the submitted values back.
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return problem(
            422,
            "validation_error",
            "Invalid request",
            "Request validation failed",
            extra={"errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        title = HTTPStatus(exc.status_code).phrase
        code = _HTTP_CODES.get(exc.status_code, f"http_{exc.status_code}")
        headers = dict(exc.headers) if exc.headers else None
        return problem(exc.status_code, code, title, title, headers=headers)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error")
        return problem(500, AppError.code, AppError.title, AppError.title)
