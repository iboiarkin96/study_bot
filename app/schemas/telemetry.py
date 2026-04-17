"""Pydantic schemas for docs-search telemetry ingestion and metrics."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DocsSearchTelemetryIngestRequest(BaseModel):
    """Client-emitted docs-search telemetry event.

    Attributes:
        event: Event name (for example ``search_query``).
        emitted_at_ms: Event epoch timestamp in milliseconds.
        page_path: Browser path where event was emitted.
        session_id: Search session identifier.
        query_id: Per-query identifier.
        query_text: Normalized query text.
        query_len: Query text length.
        tokens_count: Number of query tokens.
        results_count: Number of search results.
        result_rank: Rank of clicked result (1-based).
        result_url: Relative docs URL of clicked result.
        latency_ms: End-to-end search latency on client side.
        time_to_success_ms: Time from first query in session to first click success.
        time_to_click_ms: Time from this query to click.
        source: Interaction source (for example ``mouse_click``).
        top_results: Top-N result descriptors logged as impressions.
        payload: Arbitrary extension fields preserved in raw payload JSON.
    """

    event: str = Field(..., min_length=1, max_length=64)
    emitted_at_ms: int = Field(..., ge=0)
    page_path: str = Field(default="", max_length=512)
    session_id: str = Field(default="", max_length=128)
    query_id: str = Field(default="", max_length=128)
    query_text: str = Field(default="", max_length=1024)
    query_len: int = Field(default=0, ge=0, le=1024)
    tokens_count: int = Field(default=0, ge=0, le=128)
    results_count: int = Field(default=0, ge=0, le=10_000)
    result_rank: int = Field(default=0, ge=0, le=10_000)
    result_url: str = Field(default="", max_length=1024)
    latency_ms: int = Field(default=0, ge=0, le=60_000)
    time_to_success_ms: int = Field(default=0, ge=0, le=24 * 60 * 60 * 1000)
    time_to_click_ms: int = Field(default=0, ge=0, le=24 * 60 * 60 * 1000)
    source: str = Field(default="", max_length=64)
    top_results: list[dict[str, Any]] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class DocsSearchTelemetryMetricsResponse(BaseModel):
    """Response payload with docs-search KPI aggregates.

    Attributes:
        window_minutes: Aggregation horizon in minutes.
        total_queries: Number of ``search_query`` events in the window.
        zero_result_queries: Number of queries with empty result set.
        zero_result_rate: Ratio of zero-result queries.
        queries_with_click: Number of unique queries that got at least one click.
        query_ctr: Query-level click-through rate.
        median_time_to_first_success_ms: P50 for first success in session.
        p75_time_to_first_success_ms: P75 for first success in session.
    """

    window_minutes: int
    total_queries: int
    zero_result_queries: int
    zero_result_rate: float
    queries_with_click: int
    query_ctr: float
    median_time_to_first_success_ms: int | None
    p75_time_to_first_success_ms: int | None
