"""Request context: every response carries an X-Request-ID."""

import re

from opentelemetry import trace
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lotse.core.ids import new_id
from lotse.core.tracing import ATTR_REQUEST_ID

_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{8,64}")


class RequestContextMiddleware:
    """Accept a well-formed incoming X-Request-ID, otherwise generate one."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id", "")
        request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else str(new_id())
        scope.setdefault("state", {})["request_id"] = request_id
        trace.get_current_span().set_attribute(ATTR_REQUEST_ID, request_id)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        await self.app(scope, receive, send_with_id)
