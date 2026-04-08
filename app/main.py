"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.api.v1.user import router as user_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.validation.user import build_validation_error_payload

settings = get_settings()
log_file_path = configure_logging(settings)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Study App API",
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next) -> Response:
    """Write one structured log line for each incoming request."""
    started_at = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (perf_counter() - started_at) * 1000
        logger.exception(
            "request_failed method=%s path=%s elapsed_ms=%.2f",
            request.method,
            request.url.path,
            elapsed_ms,
        )
        raise

    elapsed_ms = (perf_counter() - started_at) * 1000
    logger.info(
        "request_done method=%s path=%s status=%s elapsed_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return stable, code-based payload for all request validation errors."""
    logger.warning("validation_error method=%s path=%s", request.method, request.url.path)
    return JSONResponse(
        status_code=422,
        content=build_validation_error_payload(request, exc),
    )


@app.get("/health", tags=["System"], summary="Health check")
def health() -> dict[str, str]:
    """Return basic service status."""
    logger.debug("health_check_called")
    return {"status": "ok"}


app.include_router(user_router, prefix="/api/v1")
logger.info("application_started env=%s log_file=%s", settings.app_env, log_file_path)
