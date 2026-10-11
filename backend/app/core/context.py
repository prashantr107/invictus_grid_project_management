"""Per-request context variables.

These contextvars carry the correlation ID and the authenticated actor across
the request lifecycle without threading them through every function signature.
They are populated by `RequestContextMiddleware` and the auth dependency.
"""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
actor_id_var: ContextVar[str | None] = ContextVar("actor_id", default=None)


def current_request_id() -> str | None:
    return request_id_var.get()


def current_actor_id() -> str | None:
    return actor_id_var.get()
