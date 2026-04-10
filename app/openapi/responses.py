"""Reusable OpenAPI response blocks shared across endpoints."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.openapi.examples import (
    IDEMPOTENCY_KEY_CONFLICT_ERROR_EXAMPLE,
    IDEMPOTENCY_KEY_REQUIRED_ERROR_EXAMPLE,
    SECURITY_AUTH_REQUIRED_ERROR_EXAMPLE,
    SECURITY_BODY_TOO_LARGE_ERROR_EXAMPLE,
    SECURITY_RATE_LIMIT_EXCEEDED_ERROR_EXAMPLE,
)
from app.schemas.errors import ApiErrorResponse


def build_common_business_400_response(
    *, extra_examples: dict[str, dict[str, object]] | None = None
) -> dict[str, Any]:
    """OpenAPI fragment for HTTP 400 business-rule failures with optional examples.

    Args:
        extra_examples: Additional named example payloads merged into ``content``.

    Returns:
        Dict suitable for a ``responses[400]`` entry in FastAPI route decorators.
    """
    examples: dict[str, dict[str, object]] = {
        "idempotency_key_missing": {
            "summary": "Missing Idempotency-Key header",
            "value": IDEMPOTENCY_KEY_REQUIRED_ERROR_EXAMPLE,
        }
    }
    if extra_examples:
        examples.update(extra_examples)
    return {
        "model": ApiErrorResponse,
        "description": "Business validation failure.",
        "content": {"application/json": {"examples": examples}},
    }


COMMON_IDEMPOTENCY_CONFLICT_409_RESPONSE: dict[str, Any] = {
    "model": ApiErrorResponse,
    "description": "Idempotency key was reused with different payload.",
    "content": {
        "application/json": {
            "examples": {
                "idempotency_conflict": {
                    "summary": "Idempotency key conflict",
                    "value": IDEMPOTENCY_KEY_CONFLICT_ERROR_EXAMPLE,
                }
            }
        }
    },
}

COMMON_AUTH_REQUIRED_401_RESPONSE: dict[str, Any] = {
    "model": ApiErrorResponse,
    "description": "Missing or invalid API key header.",
    "content": {
        "application/json": {
            "examples": {
                "auth_required": {
                    "summary": "Auth header required",
                    "value": SECURITY_AUTH_REQUIRED_ERROR_EXAMPLE,
                }
            }
        }
    },
}

COMMON_BODY_TOO_LARGE_413_RESPONSE: dict[str, Any] = {
    "model": ApiErrorResponse,
    "description": "Request body exceeds configured maximum size.",
    "content": {
        "application/json": {
            "examples": {
                "body_too_large": {
                    "summary": "Body size limit exceeded",
                    "value": SECURITY_BODY_TOO_LARGE_ERROR_EXAMPLE,
                }
            }
        }
    },
}

COMMON_RATE_LIMIT_429_RESPONSE: dict[str, Any] = {
    "model": ApiErrorResponse,
    "description": "Per-client request rate limit exceeded.",
    "headers": {
        "Retry-After": {
            "description": "Seconds until request can be retried.",
            "schema": {"type": "string"},
        },
        "X-RateLimit-Limit": {
            "description": "Rate-limit ceiling for current window.",
            "schema": {"type": "string"},
        },
        "X-RateLimit-Remaining": {
            "description": "Remaining requests in current window.",
            "schema": {"type": "string"},
        },
    },
    "content": {
        "application/json": {
            "examples": {
                "rate_limit_exceeded": {
                    "summary": "Too many requests",
                    "value": SECURITY_RATE_LIMIT_EXCEEDED_ERROR_EXAMPLE,
                }
            }
        }
    },
}


def common_protected_route_responses() -> dict[int | str, dict[str, Any]]:
    """401 and 429 response blocks copied for injection into route ``responses`` maps.

    Returns:
        Mapping of status code to OpenAPI response dict (deep copies for safe mutation).
    """
    return {
        401: deepcopy(COMMON_AUTH_REQUIRED_401_RESPONSE),
        429: deepcopy(COMMON_RATE_LIMIT_429_RESPONSE),
    }
