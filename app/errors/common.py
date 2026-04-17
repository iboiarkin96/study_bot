"""Service-wide ``COMMON_*`` stable errors (transport, idempotency, generic validation)."""

from __future__ import annotations

from app.errors.types import StableError

# Generic fallback when no specific Pydantic (field, type) rule matches.
COMMON_000 = StableError(
    "COMMON_000",
    "COMMON_VALIDATION_ERROR",
    "Request validation failed.",
)

COMMON_400 = StableError(
    "COMMON_400",
    "IDEMPOTENCY_KEY_REQUIRED",
    "Missing required `Idempotency-Key` header for write operation.",
)

COMMON_401 = StableError(
    "COMMON_401",
    "SECURITY_AUTH_REQUIRED",
    "Missing or invalid API key in header `X-API-Key`.",
)

COMMON_409 = StableError(
    "COMMON_409",
    "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
    "Idempotency key was already used with another payload.",
)

COMMON_413 = StableError(
    "COMMON_413",
    "SECURITY_REQUEST_BODY_TOO_LARGE",
    "Request body exceeds configured maximum size.",
)

COMMON_429 = StableError(
    "COMMON_429",
    "SECURITY_RATE_LIMIT_EXCEEDED",
    "Too many requests. Retry later.",
)

COMMON_500 = StableError(
    "COMMON_500",
    "SECURITY_AUTH_STRATEGY_INVALID",
    "Unsupported API authentication configuration.",
)
