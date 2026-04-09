"""Prometheus metrics utilities for API observability."""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from sqlalchemy import event

if TYPE_CHECKING:
    from fastapi import Request
    from sqlalchemy.engine import Engine


def _status_class(status_code: int) -> str:
    return f"{status_code // 100}xx"


def _db_operation(statement: str) -> str:
    normalized = statement.strip().split(" ", 1)[0].upper()
    if normalized == "SELECT":
        return "read"
    if normalized in {"INSERT", "UPDATE", "DELETE"}:
        return "write"
    if normalized in {"BEGIN", "COMMIT", "ROLLBACK"}:
        return "tx"
    return "other"


class MetricsCollector:
    """Application-level Prometheus metrics collector."""

    def __init__(
        self,
        *,
        enabled: bool,
        metrics_path: str,
        http_buckets: tuple[float, ...],
        db_buckets: tuple[float, ...],
    ) -> None:
        self.enabled = enabled
        self.metrics_path = metrics_path
        self.registry = CollectorRegistry()

        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests by method/path/status.",
            ("method", "path_template", "status_code"),
            registry=self.registry,
        )
        self.http_request_duration_seconds = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency in seconds.",
            ("method", "path_template", "status_class"),
            buckets=http_buckets,
            registry=self.registry,
        )
        self.http_requests_in_flight = Gauge(
            "http_requests_in_flight",
            "Current in-flight HTTP requests.",
            registry=self.registry,
        )
        self.db_operation_duration_seconds = Histogram(
            "db_operation_duration_seconds",
            "Database operation latency in seconds.",
            ("operation",),
            buckets=db_buckets,
            registry=self.registry,
        )

    @staticmethod
    def route_template(request: Request) -> str:
        route = request.scope.get("route")
        path = getattr(route, "path", None)
        if isinstance(path, str) and path:
            return path
        return request.url.path

    def should_skip_request(self, request: Request) -> bool:
        return not self.enabled or request.url.path == self.metrics_path

    def on_request_start(self, request: Request) -> float | None:
        if self.should_skip_request(request):
            return None
        self.http_requests_in_flight.inc()
        return perf_counter()

    def on_request_complete(
        self, *, request: Request, status_code: int, started_at: float | None
    ) -> None:
        if started_at is None or self.should_skip_request(request):
            return
        elapsed_s = max(perf_counter() - started_at, 0.0)
        path_template = self.route_template(request)
        method = request.method.upper()
        self.http_requests_total.labels(
            method=method,
            path_template=path_template,
            status_code=str(status_code),
        ).inc()
        self.http_request_duration_seconds.labels(
            method=method,
            path_template=path_template,
            status_class=_status_class(status_code),
        ).observe(elapsed_s)
        self.http_requests_in_flight.dec()

    def observe_db_duration(self, *, operation: str, elapsed_seconds: float) -> None:
        if not self.enabled:
            return
        self.db_operation_duration_seconds.labels(operation=operation).observe(
            max(elapsed_seconds, 0.0)
        )

    def render(self) -> bytes:
        return generate_latest(self.registry)


_INSTALLED_SQL_HOOKS: set[int] = set()


def install_sqlalchemy_metrics(*, engine: Engine, metrics: MetricsCollector) -> None:
    """Attach SQLAlchemy event hooks to capture DB latency metrics."""
    engine_id = id(engine)
    if engine_id in _INSTALLED_SQL_HOOKS:
        return
    _INSTALLED_SQL_HOOKS.add(engine_id)

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany) -> None:
        if not metrics.enabled:
            return
        context._metrics_started_at = perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany) -> None:
        if not metrics.enabled:
            return
        started_at = getattr(context, "_metrics_started_at", None)
        if not isinstance(started_at, float):
            return
        metrics.observe_db_duration(
            operation=_db_operation(statement),
            elapsed_seconds=perf_counter() - started_at,
        )


def metrics_content_type() -> str:
    """Expose Prometheus content type for `/metrics` endpoint."""
    return CONTENT_TYPE_LATEST
