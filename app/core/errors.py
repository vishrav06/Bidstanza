"""
Error model and exception handlers for Bidstanza.

Every failure the API returns uses one JSON envelope:

    {"error": {"code": "bid_too_low", "message": "...", "details": {...}}}

Domain code raises subclasses of `AppError` (for example `raise BidTooLow(...)`)
and never builds HTTP responses itself. The handlers registered by
`register_exception_handlers()` translate these exceptions, along with FastAPI's
validation errors, Starlette's routing errors and any unexpected crash, into that
envelope. Clients can then branch on a stable machine-readable `code` instead of
parsing message text.
"""

import logging
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Exception hierarchy
# --------------------------------------------------------------------------- #
class AppError(Exception):
    """Base class for all expected, client-facing errors.

    Subclasses set `status_code`, `code` and a default `message` as class
    attributes. Callers may override the message or attach `details`.
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details or {}
        self.headers = headers
        super().__init__(self.message)


class Unauthorized(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    message = "Authentication credentials are missing or invalid."

    def __init__(self, message: str | None = None, **kwargs: Any) -> None:
        # RFC 6750: 401 responses for bearer auth should advertise the scheme.
        kwargs.setdefault("headers", {"WWW-Authenticate": "Bearer"})
        super().__init__(message, **kwargs)


class Forbidden(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    message = "You are not allowed to perform this action."


class NotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Resource not found."

    def __init__(self, resource: str, resource_id: Any) -> None:
        super().__init__(
            f"{resource} {resource_id} not found.",
            details={"resource": resource, "id": resource_id},
        )


class Conflict(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "The request conflicts with the current state of the resource."


class AuctionNotActive(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "auction_not_active"
    message = "This auction is no longer accepting bids."


class AuctionExpired(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "auction_expired"
    message = "This auction has ended."


class SelfOutbid(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "self_outbid"
    message = "You are already the highest bidder."


class SellerCannotBid(Forbidden):
    code = "seller_cannot_bid"
    message = "Sellers cannot bid on their own auctions."


class BidTooLow(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "bid_too_low"
    message = "Bid is below the minimum required amount."

    def __init__(self, minimum_required: Decimal) -> None:
        # Money is serialized as a string everywhere so clients never see float rounding.
        super().__init__(
            f"Bid must be at least {minimum_required}.",
            details={"minimum_required": str(minimum_required)},
        )


# --------------------------------------------------------------------------- #
# Response helpers & handlers
# --------------------------------------------------------------------------- #
def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build the standard error envelope. The only place the shape is defined."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or {}}},
        headers=headers,
    )


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Pydantic's raw error dicts can carry non-JSON-serializable objects in `ctx`,
    # so keep only the stable, useful fields.
    errors = [
        {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
        for err in exc.errors()
    ]
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "validation_error",
        "Request validation failed.",
        {"errors": errors},
    )


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Covers framework-raised errors: unknown route (404), wrong method (405), etc.
    return error_response(
        exc.status_code,
        "http_error",
        str(exc.detail),
        headers=getattr(exc, "headers", None),
    )


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    # Log the full traceback server-side; never leak internals to the client.
    logger.exception("Unhandled error", exc_info=exc)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, AppError.code, AppError.message
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all handlers to the app. Called once from main.py."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    