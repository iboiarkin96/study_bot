"""Shared error response schemas for OpenAPI documentation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ApiErrorResponse(BaseModel):
    """Business error payload with stable code."""

    code: str
    key: str
    message: str
    source: str


class ValidationErrorItem(BaseModel):
    """Normalized validation error with stable code and details."""

    code: str
    key: str
    message: str
    field: str | None = None
    source: str
    details: dict[str, Any] | None = None


class ValidationErrorResponse(BaseModel):
    """Validation error envelope used by 422 responses."""

    error_type: str
    endpoint: str
    errors: list[ValidationErrorItem]


class LegacyValidationErrorItem(BaseModel):
    """Legacy shape left for transitional docs and reference."""

    type: str
    loc: list[str | int]
    msg: str
    input: Any
    ctx: dict[str, Any] | None = None

