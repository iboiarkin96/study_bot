"""FastAPI application entrypoint.

Registers middleware (logging, body size, auth, rate limit, security headers), exception
handlers, health and metrics routes, and the versioned API router. Application settings and
logging are initialized at import time.
"""

from __future__ import annotations

import logging
import os
import time
from time import perf_counter
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.responses import Response

from app.api.v1.user import router as user_router
from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.docs_search_telemetry import DocsSearchTelemetryStore
from app.core.logging import configure_logging
from app.core.metrics import MetricsCollector, install_sqlalchemy_metrics, metrics_content_type
from app.core.request_context import (
    new_request_id,
    normalize_request_id_header,
    request_id_var,
    reset_request_context,
)
from app.core.security import (
    InMemoryRateLimiter,
    apply_security_headers,
    authenticate_request,
    build_security_error_payload,
    extract_client_id,
    is_protected_api_request,
)
from app.errors.common import COMMON_413, COMMON_429
from app.schemas.errors import ValidationErrorResponse
from app.schemas.system import LiveResponse, ReadyResponse
from app.schemas.telemetry import (
    DocsSearchTelemetryIngestRequest,
    DocsSearchTelemetryMetricsResponse,
)
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

DESCRIPTION = "ETR Study App API. The API is versioned with the code, readable in the browser."


SERVERS = [
    {"url": "http://localhost:8000", "description": "Local development (localhost)"},
]

app = FastAPI(
    title=settings.app_name,
    version="1.1.1",
    description=DESCRIPTION,
    docs_url=None,
    redoc_url=None,
    openapi_tags=OPENAPI_TAGS,
    servers=SERVERS,
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
docs_search_telemetry_store = DocsSearchTelemetryStore(settings.sqlite_db_path)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list[str](settings.cors_allow_origins),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=list[str](settings.cors_allow_methods),
    allow_headers=list[str](settings.cors_allow_headers),
    expose_headers=list[str](settings.cors_expose_headers),
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
                    COMMON_413,
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
                    "detail": build_security_error_payload(COMMON_429),
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


@app.middleware("http")
async def request_context_middleware(request: Request, call_next) -> Response:
    """Bind ``X-Request-Id`` (client-supplied or generated) for logging and response headers.

    Registered last so it runs first on the request path, ensuring downstream logs include
    ``request_id``. ``trace_id`` / ``span_id`` stay empty until OpenTelemetry is added.

    Args:
        request: Incoming ASGI request.
        call_next: Next middleware or route handler.

    Returns:
        Downstream response with ``X-Request-Id`` set.
    """
    incoming = normalize_request_id_header(request.headers.get("X-Request-Id"))
    rid = incoming or new_request_id()
    token = request_id_var.set(rid)
    try:
        response = await call_next(request)
    finally:
        reset_request_context(token)
    response.headers["X-Request-Id"] = rid
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
    """Liveness: process is up (no dependency checks).

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

DOCS_SEARCH_TELEMETRY_422_EXAMPLES = {
    "missing_event": {
        "summary": "Missing required event field",
        "value": {
            "error_type": "validation_error",
            "endpoint": "POST /internal/telemetry/docs-search",
            "errors": [
                {
                    "code": "USER_001",
                    "key": "field_required",
                    "message": "Field required",
                    "field": "event",
                    "source": "validation",
                    "details": {
                        "type": "missing",
                        "loc": ["body", "event"],
                        "input": {
                            "emitted_at_ms": 1776420000000,
                            "session_id": "s_123",
                            "query_id": "q_123",
                        },
                        "ctx": None,
                    },
                }
            ],
        },
    }
}


@app.post(
    "/internal/telemetry/docs-search",
    tags=["System"],
    summary="Ingest docs search telemetry event",
    operation_id="ingestDocsSearchTelemetryEvent",
    status_code=202,
    responses={
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ValidationErrorResponse,
            "description": "Validation error for malformed telemetry payload.",
            "content": {
                "application/json": {
                    "examples": DOCS_SEARCH_TELEMETRY_422_EXAMPLES,
                }
            },
        }
    },
)
def ingest_docs_search_telemetry(
    payload: DocsSearchTelemetryIngestRequest,
) -> dict[str, str]:
    """Persist one docs-search client telemetry event to the technical SQLite DB.

    Args:
        payload: Normalized telemetry event body from docs frontend JS.

    Returns:
        Lightweight acknowledgement body.
    """
    persisted_payload = payload.model_dump(mode="json")
    extra_payload = persisted_payload.pop("payload", {})
    if isinstance(extra_payload, dict):
        persisted_payload.update(extra_payload)
    docs_search_telemetry_store.insert_event(persisted_payload)
    return {"status": "accepted"}


@app.get(
    "/internal/telemetry/docs-search/metrics",
    tags=["System"],
    summary="Get docs search KPI summary",
    operation_id="getDocsSearchTelemetryMetrics",
    response_model=DocsSearchTelemetryMetricsResponse,
)
def get_docs_search_telemetry_metrics(
    window_minutes: int = 24 * 60,
) -> DocsSearchTelemetryMetricsResponse:
    """Return docs-search KPI aggregates for the requested rolling time window.

    Args:
        window_minutes: Rolling aggregation horizon (default 24 hours).

    Returns:
        KPI summary with zero-result rate, query CTR, and time-to-first-success percentiles.
    """
    bounded_window = min(max(1, int(window_minutes)), 30 * 24 * 60)
    snapshot = docs_search_telemetry_store.metrics(
        now_ms=int(time.time() * 1000),
        window_minutes=bounded_window,
    )
    return DocsSearchTelemetryMetricsResponse(
        window_minutes=snapshot.window_minutes,
        total_queries=snapshot.total_queries,
        zero_result_queries=snapshot.zero_result_queries,
        zero_result_rate=snapshot.zero_result_rate,
        queries_with_click=snapshot.queries_with_click,
        query_ctr=snapshot.query_ctr,
        median_time_to_first_success_ms=snapshot.median_time_to_first_success_ms,
        p75_time_to_first_success_ms=snapshot.p75_time_to_first_success_ms,
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


def custom_openapi() -> dict[str, Any]:
    """Build OpenAPI schema and document ``X-Request-Id`` on every operation for Swagger UI."""
    if app.openapi_schema is not None:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    from app.openapi.request_id_openapi import enrich_openapi_with_request_id

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
        servers=app.servers,
    )
    enrich_openapi_with_request_id(openapi_schema)
    app.openapi_schema = openapi_schema
    return app.openapi_schema


setattr(app, "openapi", custom_openapi)  # noqa: B010 -- mypy rejects direct assignment to FastAPI.openapi


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
