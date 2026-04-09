"""Pydantic schemas for system endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LiveResponse(BaseModel):
    """Response payload for liveness endpoint."""

    status: str = Field(default="alive", examples=["alive"])
    app_env: str = Field(
        ...,
        description="Logical deployment profile from APP_ENV (dev, qa, prod).",
        examples=["dev", "qa", "prod"],
    )


class ReadyResponse(BaseModel):
    """Response payload for readiness endpoint."""

    status: str = Field(default="ready", examples=["ready", "not_ready"])
    checks: dict[str, str] = Field(default_factory=dict)
    db_latency_ms: float | None = Field(default=None, examples=[1.42, None])
