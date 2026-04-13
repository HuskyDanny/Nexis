"""Global error handlers — consistent ErrorResponse shape for all failures."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.core.config import settings
from src.core.logger import get_logger
from src.middleware.request_logging import REQUEST_ID_KEY

log = get_logger("errors")


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    request_id: str | None = None


def _get_request_id(request: Request) -> str | None:
    """Extract request ID from scope (set by RequestMiddleware)."""
    return request.scope.get(REQUEST_ID_KEY)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception):
        request_id = _get_request_id(request)
        log.error("Unhandled exception [%s]: %s", request_id, exc, exc_info=True)
        detail = (
            str(exc)
            if settings.environment == "development"
            else "An unexpected error occurred"
        )
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error", detail=detail, request_id=request_id
            ).model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = _get_request_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=str(exc.detail), request_id=request_id
            ).model_dump(),
        )
