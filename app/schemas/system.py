"""Pydantic schemas for system endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response payload for health check endpoint."""

    status: str = Field(default="ok", examples=["ok"])
