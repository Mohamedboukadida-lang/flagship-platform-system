"""Request context: a request id on every response and one access log line per request."""

import logging
import re
import time

from opentelemetry import trace
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lotse.core.ids import new_id
from lotse.core.logging import request_id_var
from lotse.core.tracing import ATTR_REQUEST_ID, current_trace_id

access_log = logging.getLogger("lotse.access")

_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{8,64}")
# Probes run every few seconds; their successes would drown the log.
_QUIET_PATHS = frozenset({"/healthz", "/readyz"})


class RequestContextMiddleware:
    """Accept a well-formed incoming X-Request-ID, otherwise generate one, and log the request.

    The access line holds the method, path, status, ids and timing only. It never holds the
    query string, headers or bodies, so tokens and user content cannot reach the log through it.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id", "")
        request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else str(new_id())
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        trace.get_current_span().set_attribute(ATTR_REQUEST_ID, request_id)
        token = request_id_var.set(request_id)

        status = 500  # stays 500 if the app raises before a response starts
        started = time.perf_counter()

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            path = scope["path"]
            if not (path.endswith(tuple(_QUIET_PATHS)) and status < 400):
                principal = state.get("principal")
                access_log.info(
                    "request",
                    extra={
                        # Stamped on the record, so a handler that formats later keeps them.
                        "request_id": request_id,
                        "trace_id": current_trace_id(),
                        "method": scope["method"],
                        "path": path[:200],
                        "status": status,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                        "tenant_id": str(principal.tenant_id) if principal else None,
                        "user_id": str(principal.user_id) if principal else None,
                    },
                )
            request_id_var.reset(token)
