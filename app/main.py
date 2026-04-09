"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from base64 import b64decode
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.api.v1.user import router as user_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import (
    InMemoryRateLimiter,
    apply_security_headers,
    authenticate_request,
    build_security_error_payload,
    extract_client_id,
    is_protected_api_request,
)
from app.schemas.system import HealthResponse
from app.validation.user import build_validation_error_payload

settings = get_settings()
log_file_path = configure_logging(settings)
logger = logging.getLogger(__name__)

OPENAPI_TAGS = [
    {
        "name": "System",
        "description": "Operational service endpoints (health/readiness and platform metadata).",
    },
    {
        "name": "User",
        "description": "User identity lifecycle endpoints with idempotency and contract-driven errors.",
    },
]

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Study App API",
    docs_url=None,
    redoc_url=None,
    openapi_tags=OPENAPI_TAGS,
)
rate_limiter = InMemoryRateLimiter(
    limit=settings.api_rate_limit_requests,
    window_seconds=settings.api_rate_limit_window_seconds,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allow_origins),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=list(settings.cors_allow_methods),
    allow_headers=list(settings.cors_allow_headers),
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


@app.middleware("http")
async def request_body_limit_middleware(request: Request, call_next) -> Response:
    """Reject requests with payload larger than configured API limit."""
    raw = await request.body()
    if len(raw) > settings.api_body_max_bytes:
        logger.warning(
            "request_body_limit_exceeded path=%s size=%s max=%s",
            request.url.path,
            len(raw),
            settings.api_body_max_bytes,
        )
        return JSONResponse(
            status_code=413,
            content={
                "detail": build_security_error_payload(
                    code="COMMON_413",
                    key="SECURITY_REQUEST_BODY_TOO_LARGE",
                    message=f"Request body exceeds limit of {settings.api_body_max_bytes} bytes.",
                )
            },
        )
    return await call_next(request)


@app.middleware("http")
async def auth_and_rate_limit_middleware(request: Request, call_next) -> Response:
    """Apply mock auth and per-client rate limiting for protected API routes."""
    if is_protected_api_request(request, settings):
        auth_error = authenticate_request(request, settings)
        if auth_error is not None:
            return auth_error

        bucket = f"{extract_client_id(request)}:{request.url.path}"
        rate_result = rate_limiter.check(bucket)
        if not rate_result.allowed:
            logger.warning(
                "rate_limit_exceeded bucket=%s path=%s",
                bucket,
                request.url.path,
            )
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": build_security_error_payload(
                        code="COMMON_429",
                        key="SECURITY_RATE_LIMIT_EXCEEDED",
                        message="Too many requests. Retry later.",
                    )
                },
            )
            response.headers["Retry-After"] = str(rate_result.retry_after_seconds)
            response.headers["X-RateLimit-Limit"] = str(settings.api_rate_limit_requests)
            response.headers["X-RateLimit-Remaining"] = "0"
            return response

    response = await call_next(request)
    if is_protected_api_request(request, settings):
        response.headers["X-RateLimit-Limit"] = str(settings.api_rate_limit_requests)
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next) -> Response:
    """Attach baseline security headers to all responses."""
    response = await call_next(request)
    apply_security_headers(response, request.url.path)
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


@app.get("/health", tags=["System"], summary="Health check", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return basic service status."""
    logger.debug("health_check_called")
    return HealthResponse(status="ok")


@app.get("/favicon.png", include_in_schema=False)
def favicon() -> Response:
    """Serve local favicon to avoid external DNS dependency in docs UI."""
    # 1x1 transparent PNG
    png_bytes = b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7+3XQAAAAASUVORK5CYII="
    )
    return Response(content=png_bytes, media_type="image/png")


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui() -> Response:
    """Serve Swagger UI with local favicon."""
    openapi_url = app.openapi_url or "/openapi.json"
    return get_swagger_ui_html(
        openapi_url=openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_favicon_url="/favicon.png",
    )


app.include_router(user_router, prefix="/api/v1")
logger.info("application_started env=%s log_file=%s", settings.app_env, log_file_path)
