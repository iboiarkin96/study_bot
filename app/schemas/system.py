"""Pydantic schemas for system endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LiveResponse(BaseModel):
    """``GET /live`` — process up signal without dependency checks.

    Attributes:
        status: Fixed literal ``alive`` for a healthy process.
        app_env: Active ``APP_ENV`` profile (``dev``, ``qa``, ``prod``).
    """

    status: str = Field(default="alive", examples=["alive"])
    app_env: str = Field(
        ...,
        description="Logical deployment profile from APP_ENV (dev, qa, prod).",
        examples=["dev", "qa", "prod"],
    )


class ReadyResponse(BaseModel):
    """``GET /ready`` — dependency checks (used with HTTP 200 or 503).

    Attributes:
        status: ``ready`` or ``not_ready`` depending on checks.
        checks: Map of check name to short state string (e.g. ``database``).
        db_latency_ms: Observed database round-trip in milliseconds, if measured.
    """

    status: str = Field(default="ready", examples=["ready", "not_ready"])
    checks: dict[str, str] = Field(default_factory=dict)
    db_latency_ms: float | None = Field(default=None, examples=[1.42, None])
