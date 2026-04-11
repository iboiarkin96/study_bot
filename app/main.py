"""FastAPI application entrypoint.

Registers middleware (logging, body size, auth, rate limit, security headers), exception
handlers, health and metrics routes, and the versioned API router. Application settings and
logging are initialized at import time.
"""

from __future__ import annotations

import logging
import os
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.responses import Response

from app.api.v1.user import router as user_router
from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.logging import configure_logging
from app.core.metrics import MetricsCollector, install_sqlalchemy_metrics, metrics_content_type
from app.core.security import (
    InMemoryRateLimiter,
    apply_security_headers,
    authenticate_request,
    build_security_error_payload,
    extract_client_id,
    is_protected_api_request,
)
from app.schemas.system import LiveResponse, ReadyResponse
from app.validation.user import build_validation_error_payload

settings = get_settings()
log_file_path = configure_logging(settings)
logger = logging.getLogger(__name__)

OPENAPI_TAGS = [
    {
        "name": "System",
        "description": "Operational endpoints (live/ready/metrics and platform metadata).",
    },
    {
        "name": "User",
        "description": "User identity lifecycle endpoints with idempotency and contract-driven errors.",
    },
]

app = FastAPI(
    title=settings.app_name,
    version="1.1.1",
    description="Study App API",
    docs_url=None,
    redoc_url=None,
    openapi_tags=OPENAPI_TAGS,
    servers=[
        {
            "url": "http://127.0.0.1:8000",
            "description": "Local development (APP_HOST/APP_PORT default)",
        },
        {"url": "http://localhost:8000", "description": "Local development (localhost)"},
    ],
)
rate_limiter = InMemoryRateLimiter(
    limit=settings.api_rate_limit_requests,
    window_seconds=settings.api_rate_limit_window_seconds,
)
metrics = MetricsCollector(
    enabled=settings.metrics_enabled,
    metrics_path=settings.metrics_path,
    http_buckets=settings.metrics_buckets_http,
    db_buckets=settings.metrics_buckets_db,
)
install_sqlalchemy_metrics(engine=engine, metrics=metrics)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allow_origins),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=list(settings.cors_allow_methods),
    allow_headers=list(settings.cors_allow_headers),
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next) -> Response:
    """Log request duration, status, and update Prometheus HTTP metrics.

    Args:
        request: Incoming ASGI request.
        call_next: Next middleware or route handler in the stack.

    Returns:
        Downstream response, or re-raises exceptions after logging a failure line.
    """
    metrics_started_at = metrics.on_request_start(request)
    started_at = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (perf_counter() - started_at) * 1000
        metrics.on_request_complete(
            request=request,
            status_code=500,
            started_at=metrics_started_at,
        )
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
    metrics.on_request_complete(
        request=request,
        status_code=response.status_code,
        started_at=metrics_started_at,
    )
    return response


@app.middleware("http")
async def request_body_limit_middleware(request: Request, call_next) -> Response:
    """Return 413 when the raw body exceeds ``settings.api_body_max_bytes``.

    Args:
        request: Incoming request (body is read fully).
        call_next: Next handler; invoked only when under the size limit.

    Returns:
        Error JSON with ``COMMON_413`` or the downstream response.
    """
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
    """Enforce API key auth and sliding-window rate limits on protected prefixes.

    Args:
        request: Incoming request.
        call_next: Next handler.

    Returns:
        401/429 JSON, or downstream response with optional rate-limit headers.
    """
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
    """Add CSP and related headers via :func:`app.core.security.apply_security_headers`.

    Args:
        request: Incoming request (path selects CSP variant).
        call_next: Next handler.

    Returns:
        Response with security headers applied.
    """
    response = await call_next(request)
    apply_security_headers(response, request.url.path)
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Map Pydantic validation failures to the project's 422 envelope format.

    Args:
        request: Request that failed validation.
        exc: FastAPI validation exception with ``errors()`` detail list.

    Returns:
        JSON response with status 422 and a stable ``error_type`` / ``errors`` body.
    """
    logger.warning("validation_error method=%s path=%s", request.method, request.url.path)
    return JSONResponse(
        status_code=422,
        content=build_validation_error_payload(request, exc),
    )


def _readiness_probe(timeout_ms: int) -> tuple[bool, float | None, str]:
    """Execute ``SELECT 1`` against the app database and classify readiness.

    Args:
        timeout_ms: If DB latency exceeds this, the probe is treated as not ready.

    Returns:
        Tuple ``(is_ready, db_latency_ms_or_none, state)`` where ``state`` is
        ``ok``, ``timeout``, or ``db_error``.
    """
    started_at = perf_counter()
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("ready_check_failed")
        return False, None, "db_error"

    elapsed_ms = (perf_counter() - started_at) * 1000
    metrics.observe_db_duration(operation="health_check", elapsed_seconds=elapsed_ms / 1000)
    if elapsed_ms > timeout_ms:
        logger.warning(
            "ready_check_timeout elapsed_ms=%.2f timeout_ms=%s",
            elapsed_ms,
            timeout_ms,
        )
        return False, elapsed_ms, "timeout"
    return True, elapsed_ms, "ok"


# Assign as variable to simplify monkeypatching in tests.
readiness_probe = _readiness_probe


@app.get(
    "/live",
    tags=["System"],
    summary="Liveness probe",
    operation_id="getLiveProbe",
    response_model=LiveResponse,
)
def live() -> LiveResponse:
    """Kubernetes-style liveness: process is up (no dependency checks).

    Returns:
        Payload with ``status="alive"`` and current ``app_env``.
    """
    return LiveResponse(status="alive", app_env=settings.app_env)


@app.get(
    "/ready",
    tags=["System"],
    summary="Readiness probe",
    operation_id="getReadyProbe",
    response_model=ReadyResponse,
)
def ready() -> ReadyResponse | JSONResponse:
    """Readiness probe including database connectivity and latency budget.

    Returns:
        ``ReadyResponse`` with HTTP 200 when ready, or HTTP 503 with the same schema
        when the DB check fails or exceeds the timeout.
    """
    is_ready, db_latency_ms, db_state = readiness_probe(settings.readiness_db_timeout_ms)
    payload = ReadyResponse(
        status="ready" if is_ready else "not_ready",
        checks={"database": db_state},
        db_latency_ms=db_latency_ms,
    )
    if not is_ready:
        return JSONResponse(status_code=503, content=payload.model_dump(mode="json"))
    return payload


def metrics_endpoint() -> Response:
    """Prometheus scrape endpoint (disabled returns 404 when metrics are off).

    Returns:
        Plain-text exposition or a JSON error when metrics are disabled.
    """
    if not settings.metrics_enabled:
        return JSONResponse(status_code=404, content={"detail": "Metrics are disabled."})
    return Response(content=metrics.render(), media_type=metrics_content_type())


app.add_api_route(
    settings.metrics_path,
    metrics_endpoint,
    methods=["GET"],
    include_in_schema=False,
)


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui() -> Response:
    """Serve Swagger UI (hidden from OpenAPI schema; uses ``/favicon.png``).

    Returns:
        HTML page loading the interactive API docs.
    """
    openapi_url = app.openapi_url or "/openapi.json"
    return get_swagger_ui_html(
        openapi_url=openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_favicon_url="/favicon.png",
    )


app.include_router(user_router, prefix="/api/v1")


if os.getenv("LOADTEST_HTTP_500", "").lower() in ("1", "true", "yes"):

    @app.get("/__loadtest/http500", include_in_schema=False)
    def loadtest_http500() -> JSONResponse:
        """Return HTTP 500 for synthetic error-rate testing (guarded by env flag).

        Returns:
            Fixed JSON error body for observability drills.

        Note:
            Route is registered only when ``LOADTEST_HTTP_500`` is truthy.
        """
        return JSONResponse(status_code=500, content={"detail": "loadtest_http500"})


logger.info("application_started env=%s log_file=%s", settings.app_env, log_file_path)
