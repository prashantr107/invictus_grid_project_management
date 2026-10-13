"""Domain exceptions and the centralized mapping to API error responses.

Services raise the typed `AppError` subclasses below; a single set of FastAPI
exception handlers turns them (and framework errors) into one consistent JSON
shape:

    {"detail": <human message>, "code": <stable code>, "details": <safe context>,
     "request_id": <correlation id>}

`detail` is preserved as a top-level string for existing clients while `code`
and `request_id` satisfy the TRD §11 error contract. Stack traces and secrets
are never exposed.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.context import current_request_id

logger = logging.getLogger("app.errors")

_STATUS_CODES = {
    400: "bad_request",
    401: "authentication_required",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "service_unavailable",
}


class AppError(Exception):
    """Base class for expected, mapped application errors."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or type(self).message
        self.details = details
        self.headers = headers
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"
    message = "The request could not be processed."


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_required"
    message = "Authentication required."

    def __init__(self, message: str | None = None, **kwargs: Any) -> None:
        kwargs.setdefault("headers", {"WWW-Authenticate": "Bearer"})
        super().__init__(message, **kwargs)


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "You do not have permission to perform this action."


class PasswordChangeRequiredError(ForbiddenError):
    code = "password_change_required"
    message = "Password change required."


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Resource not found."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "The request conflicts with the current state of the resource."


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"
    message = "Validation failed."


def _payload(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {
        "detail": message,
        "code": code,
        "details": details,
        "request_id": current_request_id(),
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers that normalize every error into the shared shape."""

    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("app_error", extra={"code": exc.code}, exc_info=exc)
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.code, exc.message, jsonable_encoder(exc.details) if exc.details else None),
            headers=exc.headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(code, str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_payload("validation_error", "Validation failed.", jsonable_encoder(exc.errors())),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception")
        return JSONResponse(status_code=500, content=_payload("internal_error", "An unexpected error occurred."))
