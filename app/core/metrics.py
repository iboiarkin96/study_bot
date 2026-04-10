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
    """Map an HTTP status code to a coarse label for histogram series.

    Args:
        status_code: Numeric HTTP status.

    Returns:
        String like ``"2xx"``, ``"4xx"``, ``"5xx"``.
    """
    return f"{status_code // 100}xx"


def _db_operation(statement: str) -> str:
    """Classify a SQL statement for DB latency histogram ``operation`` label.

    Args:
        statement: Raw SQL string (first token inspected).

    Returns:
        One of ``read``, ``write``, ``tx``, or ``other``.
    """
    normalized = statement.strip().split(" ", 1)[0].upper()
    if normalized == "SELECT":
        return "read"
    if normalized in {"INSERT", "UPDATE", "DELETE"}:
        return "write"
    if normalized in {"BEGIN", "COMMIT", "ROLLBACK"}:
        return "tx"
    return "other"


class MetricsCollector:
    """Registers and updates Prometheus counters, histograms, and gauges for HTTP and DB."""

    def __init__(
        self,
        *,
        enabled: bool,
        metrics_path: str,
        http_buckets: tuple[float, ...],
        db_buckets: tuple[float, ...],
    ) -> None:
        """Create metric instruments on an isolated registry.

        Args:
            enabled: When False, observers are no-ops and nothing is recorded.
            metrics_path: Request path of the scrape endpoint (excluded from HTTP metrics).
            http_buckets: Histogram upper bounds in seconds for HTTP latency.
            db_buckets: Histogram upper bounds in seconds for DB latency.
        """
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
        """Best-effort OpenAPI-style path template for stable metric labels.

        Args:
            request: Current ASGI request.

        Returns:
            FastAPI route template path if available, else the raw URL path.
        """
        route = request.scope.get("route")
        path = getattr(route, "path", None)
        if isinstance(path, str) and path:
            return path
        return request.url.path

    def should_skip_request(self, request: Request) -> bool:
        """Return True if HTTP metrics must not observe this request (disabled or scrape).

        Args:
            request: Incoming request.

        Returns:
            Whether to skip in-flight and latency counters for this call.
        """
        return not self.enabled or request.url.path == self.metrics_path

    def on_request_start(self, request: Request) -> float | None:
        """Mark the start of request handling for latency measurement.

        Args:
            request: Incoming request.

        Returns:
            Monotonic timestamp from :func:`time.perf_counter`, or None if skipped.
        """
        if self.should_skip_request(request):
            return None
        self.http_requests_in_flight.inc()
        return perf_counter()

    def on_request_complete(
        self, *, request: Request, status_code: int, started_at: float | None
    ) -> None:
        """Record request duration and status; decrement in-flight gauge.

        Args:
            request: Same request instance as passed to :meth:`on_request_start`.
            status_code: Final HTTP status code.
            started_at: Value returned by :meth:`on_request_start`, or None to skip.
        """
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
        """Record one DB operation duration sample (also used by health checks).

        Args:
            operation: Short label (e.g. ``read``, ``write``, ``health_check``).
            elapsed_seconds: Non-negative duration in seconds.
        """
        if not self.enabled:
            return
        self.db_operation_duration_seconds.labels(operation=operation).observe(
            max(elapsed_seconds, 0.0)
        )

    def render(self) -> bytes:
        """Serialize all registered metrics in Prometheus text exposition format.

        Returns:
            UTF-8 encoded payload suitable for ``Content-Type`` from :func:`metrics_content_type`.
        """
        return generate_latest(self.registry)


_INSTALLED_SQL_HOOKS: set[int] = set()


def install_sqlalchemy_metrics(*, engine: Engine, metrics: MetricsCollector) -> None:
    """Attach before/after cursor hooks to ``engine`` once (idempotent per engine id).

    Args:
        engine: SQLAlchemy :class:`~sqlalchemy.engine.Engine` to instrument.
        metrics: Target collector for ``db_operation_duration_seconds`` samples.
    """
    engine_id = id(engine)
    if engine_id in _INSTALLED_SQL_HOOKS:
        return
    _INSTALLED_SQL_HOOKS.add(engine_id)

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany) -> None:
        """Store monotonic start time on the execution context for DB latency."""
        if not metrics.enabled:
            return
        context._metrics_started_at = perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany) -> None:
        """Observe elapsed time since ``before_cursor_execute`` for this statement."""
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
    """Return the standard Prometheus text exposition MIME type.

    Returns:
        Value suitable for the ``media_type`` of the metrics HTTP response.
    """
    return CONTENT_TYPE_LATEST
