"""Shared error response schemas for OpenAPI documentation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ApiErrorResponse(BaseModel):
    """Standard error ``detail`` object for 4xx/5xx business and security failures.

    Attributes:
        code: Project-wide stable error code.
        key: Machine-readable key for clients.
        message: Human-readable English message.
        source: Origin layer (e.g. ``business``, ``security``).
    """

    code: str
    key: str
    message: str
    source: str


class ValidationErrorItem(BaseModel):
    """Single entry in the ``errors`` array of a 422 response.

    Attributes:
        code: Stable validation error code (e.g. ``USER_001``).
        key: Machine-readable key.
        message: Human-readable message for this failure.
        field: JSON field name when applicable.
        source: Always ``validation`` for this model.
        details: Raw Pydantic context (``loc``, ``type``, ``input``, etc.).
    """

    code: str
    key: str
    message: str
    field: str | None = None
    source: str
    details: dict[str, Any] | None = None


class ValidationErrorResponse(BaseModel):
    """Top-level body for HTTP 422 validation failures.

    Attributes:
        error_type: Fixed discriminator (e.g. ``validation_error``).
        endpoint: ``METHOD path`` string for the failing request.
        errors: List of :class:`ValidationErrorItem` entries.
    """

    error_type: str
    endpoint: str
    errors: list[ValidationErrorItem]


class LegacyValidationErrorItem(BaseModel):
    """Pydantic v1-style error item kept for documentation compatibility only.

    Attributes:
        type: Pydantic error type string.
        loc: Location path segments.
        msg: Original message string.
        input: Submitted value that failed validation.
        ctx: Optional extra context from Pydantic.
    """

    type: str
    loc: list[str | int]
    msg: str
    input: Any
    ctx: dict[str, Any] | None = None
