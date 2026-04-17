"""Security helpers for API defaults (auth, limits, headers)."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic

from fastapi import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings
from app.errors.common import COMMON_401, COMMON_500
from app.errors.types import StableError


def build_security_error_payload(err: StableError, *, message: str | None = None) -> dict[str, str]:
    """Build the ``detail`` object for security-related HTTP error responses.

    Args:
        err: Stable identity from :mod:`app.errors.common` (or another catalog module).
        message: Optional override; defaults to ``err.message``.

    Returns:
        Dict with keys ``code``, ``key``, ``message``, and fixed ``source="security"``.
    """
    return err.as_detail("security", message=message)


@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of a rate-limit check for one logical bucket.

    Attributes:
        allowed: Whether the current request may proceed.
        remaining: Estimated remaining quota in the current window (best-effort).
        retry_after_seconds: Suggested ``Retry-After`` when ``allowed`` is False.
    """

    allowed: bool
    remaining: int
    retry_after_seconds: int


class InMemoryRateLimiter:
    """Process-local fixed-window rate limiter (not shared across workers)."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        """Initialize limiter state.

        Args:
            limit: Maximum number of allowed hits per ``bucket`` within one window.
            window_seconds: Rolling window length in seconds (monotonic clock).
        """
        self._limit = limit
        self._window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, bucket: str) -> RateLimitResult:
        """Record one hit for ``bucket`` and return whether the limit is exceeded.

        Args:
            bucket: Arbitrary key (e.g. ``client_id:path``).

        Returns:
            Allow/deny decision with optional retry hint.
        """
        now = monotonic()
        window_start = now - self._window_seconds
        with self._lock:
            events = self._hits[bucket]
            while events and events[0] <= window_start:
                events.popleft()

            if len(events) >= self._limit:
                retry_after = max(1, int(self._window_seconds - (now - events[0])))
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )

            events.append(now)
            remaining = max(0, self._limit - len(events))
            return RateLimitResult(
                allowed=True,
                remaining=remaining,
                retry_after_seconds=0,
            )


def apply_security_headers(response: Response, request_path: str) -> None:
    """Set baseline security headers; relax CSP slightly for Swagger UI paths.

    Args:
        response: Outgoing Starlette/FastAPI response (mutated in place).
        request_path: URL path, used to choose Content-Security-Policy for ``/docs``.
    """
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request_path.startswith("/docs") or request_path.startswith("/redoc"):
        # Swagger/ReDoc load assets from jsdelivr; keep policy strict but compatible.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "base-uri 'none'; "
            "frame-ancestors 'none'; "
            "form-action 'none'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://fastapi.tiangolo.com; "
            "font-src 'self' data: https://cdn.jsdelivr.net; "
            "connect-src 'self'"
        )
        return

    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    )


def extract_client_id(request: Request) -> str:
    """Derive a stable client identifier for rate limiting and logging.

    Args:
        request: Incoming ASGI request.

    Returns:
        First address from ``X-Forwarded-For``, else ``request.client.host``, else a fallback string.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown-client"


def is_protected_api_request(request: Request, settings: Settings) -> bool:
    """Return whether the request must go through auth and rate-limit middleware.

    Args:
        request: Incoming ASGI request.
        settings: Application settings (path prefix, etc.).

    Returns:
        ``False`` for ``OPTIONS``; otherwise ``True`` if the path starts with
        ``settings.api_protected_prefix``.
    """
    if request.method.upper() == "OPTIONS":
        return False
    return request.url.path.startswith(settings.api_protected_prefix)


def authenticate_request(request: Request, settings: Settings) -> JSONResponse | None:
    """Validate credentials according to ``settings.api_auth_strategy``.

    Args:
        request: Incoming ASGI request (headers inspected).
        settings: Auth strategy and secret configuration.

    Returns:
        ``None`` if the request is allowed, otherwise a ready-to-send error
        :class:`~starlette.responses.JSONResponse` (401 or 500).
    """
    strategy = settings.api_auth_strategy.strip().lower()
    if strategy in {"disabled", "none", "off"}:
        return None

    if strategy == "mock_api_key":
        provided_key = request.headers.get(settings.api_auth_header)
        if provided_key == settings.api_mock_api_key:
            return None
        return JSONResponse(
            status_code=401,
            content={
                "detail": build_security_error_payload(
                    COMMON_401,
                    message=(f"Missing or invalid API key in header `{settings.api_auth_header}`."),
                )
            },
        )

    return JSONResponse(
        status_code=500,
        content={
            "detail": build_security_error_payload(
                COMMON_500,
                message=f"Unsupported auth strategy: `{settings.api_auth_strategy}`.",
            )
        },
    )
