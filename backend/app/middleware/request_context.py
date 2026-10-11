"""ASGI middleware that assigns a request ID and emits access logs."""

import time
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.context import actor_id_var, request_id_var
from app.core.logging import get_logger

access_logger = get_logger("app.access")
REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware:
    """Attach a correlation ID and structured access log to every HTTP request.

    Implemented as a pure ASGI middleware (not `BaseHTTPMiddleware`) so the
    contextvars populated deeper in the stack — notably the authenticated actor
    ID set by the auth dependency — remain visible when the request completes.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = Headers(scope=scope).get(REQUEST_ID_HEADER) or uuid4().hex
        request_token = request_id_var.set(request_id)
        actor_token = actor_id_var.set(None)
        method = scope["method"]
        path = scope["path"]
        start = time.perf_counter()
        status_holder = {"status": 500}

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            access_logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "actor_id": actor_id_var.get(),
                    "method": method,
                    "path": path,
                    "status": status_holder["status"],
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                },
            )
            raise
        finally:
            access_logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "actor_id": actor_id_var.get(),
                    "method": method,
                    "path": path,
                    "status": status_holder["status"],
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                },
            )
            request_id_var.reset(request_token)
            actor_id_var.reset(actor_token)
