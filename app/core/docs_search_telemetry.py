"""Storage and aggregations for docs search telemetry events."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class DocsSearchTelemetryMetrics:
    """Computed docs-search product metrics for a time window.

    Attributes:
        window_minutes: Aggregation horizon in minutes.
        total_queries: Number of ``search_query`` events in the window.
        zero_result_queries: Number of queries with ``results_count == 0``.
        zero_result_rate: Share of zero-result queries in ``[0, 1]``.
        queries_with_click: Number of unique queries that got at least one click.
        query_ctr: Share of queries with at least one click in ``[0, 1]``.
        median_time_to_first_success_ms: P50 over first success per session.
        p75_time_to_first_success_ms: P75 over first success per session.
    """

    window_minutes: int
    total_queries: int
    zero_result_queries: int
    zero_result_rate: float
    queries_with_click: int
    query_ctr: float
    median_time_to_first_success_ms: int | None
    p75_time_to_first_success_ms: int | None


class DocsSearchTelemetryStore:
    """Append-only SQLite storage for docs-search telemetry events."""

    def __init__(self, db_path: str) -> None:
        """Initialize store and ensure schema.

        Args:
            db_path: SQLite file path used by the application runtime.
        """
        path = Path(db_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = path
        self._lock = Lock()
        self._ensure_schema()

    def _connection(self) -> sqlite3.Connection:
        """Return a configured SQLite connection.

        Returns:
            Open connection with row access by column name.
        """
        conn = sqlite3.connect(self._db_path, timeout=5.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        """Create telemetry schema and indexes if absent."""
        with self._lock, self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS docs_search_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    emitted_at_ms INTEGER NOT NULL,
                    event TEXT NOT NULL,
                    page_path TEXT,
                    session_id TEXT,
                    query_id TEXT,
                    query_text TEXT,
                    query_len INTEGER,
                    tokens_count INTEGER,
                    results_count INTEGER,
                    result_rank INTEGER,
                    result_url TEXT,
                    latency_ms INTEGER,
                    time_to_success_ms INTEGER,
                    time_to_click_ms INTEGER,
                    source TEXT,
                    top_results_json TEXT,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_docs_search_events_event_ts "
                "ON docs_search_events(event, emitted_at_ms)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_docs_search_events_query_id "
                "ON docs_search_events(query_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_docs_search_events_session_id "
                "ON docs_search_events(session_id)"
            )

    def insert_event(self, payload: dict[str, Any]) -> None:
        """Persist one telemetry event payload.

        Args:
            payload: Raw event JSON body from docs UI.
        """
        top_results = payload.get("top_results")
        top_results_json = (
            json.dumps(top_results, ensure_ascii=False) if top_results is not None else None
        )
        payload_json = json.dumps(payload, ensure_ascii=False)
        with self._lock, self._connection() as conn:
            conn.execute(
                """
                INSERT INTO docs_search_events(
                    emitted_at_ms,
                    event,
                    page_path,
                    session_id,
                    query_id,
                    query_text,
                    query_len,
                    tokens_count,
                    results_count,
                    result_rank,
                    result_url,
                    latency_ms,
                    time_to_success_ms,
                    time_to_click_ms,
                    source,
                    top_results_json,
                    payload_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    int(payload.get("emitted_at_ms", 0) or 0),
                    str(payload.get("event", "")),
                    str(payload.get("page_path", "")),
                    str(payload.get("session_id", "")),
                    str(payload.get("query_id", "")),
                    str(payload.get("query_text", "")),
                    int(payload.get("query_len", 0) or 0),
                    int(payload.get("tokens_count", 0) or 0),
                    int(payload.get("results_count", 0) or 0),
                    int(payload.get("result_rank", 0) or 0),
                    str(payload.get("result_url", "")),
                    int(payload.get("latency_ms", 0) or 0),
                    int(payload.get("time_to_success_ms", 0) or 0),
                    int(payload.get("time_to_click_ms", 0) or 0),
                    str(payload.get("source", "")),
                    top_results_json,
                    payload_json,
                ),
            )

    def metrics(self, *, now_ms: int, window_minutes: int) -> DocsSearchTelemetryMetrics:
        """Compute search KPI aggregates for the requested horizon.

        Args:
            now_ms: Current epoch milliseconds.
            window_minutes: Rolling aggregation window size.

        Returns:
            Aggregated docs-search KPI set.
        """
        since_ms = max(0, now_ms - (window_minutes * 60_000))
        with self._lock, self._connection() as conn:
            total_queries = int(
                conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM docs_search_events
                    WHERE event = 'search_query' AND emitted_at_ms >= ?
                    """,
                    (since_ms,),
                ).fetchone()["c"]
            )
            zero_result_queries = int(
                conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM docs_search_events
                    WHERE event = 'search_query' AND emitted_at_ms >= ? AND results_count = 0
                    """,
                    (since_ms,),
                ).fetchone()["c"]
            )
            queries_with_click = int(
                conn.execute(
                    """
                    SELECT COUNT(DISTINCT q.query_id) AS c
                    FROM docs_search_events q
                    WHERE q.event = 'search_query'
                      AND q.emitted_at_ms >= ?
                      AND EXISTS (
                          SELECT 1
                          FROM docs_search_events c
                          WHERE c.event = 'search_result_click'
                            AND c.query_id = q.query_id
                            AND c.emitted_at_ms >= ?
                      )
                    """,
                    (since_ms, since_ms),
                ).fetchone()["c"]
            )
            success_times = [
                int(row["time_to_success_ms"])
                for row in conn.execute(
                    """
                    SELECT MIN(time_to_success_ms) AS time_to_success_ms
                    FROM docs_search_events
                    WHERE event = 'search_success'
                      AND emitted_at_ms >= ?
                      AND time_to_success_ms > 0
                    GROUP BY session_id
                    ORDER BY time_to_success_ms ASC
                    """,
                    (since_ms,),
                ).fetchall()
                if row["time_to_success_ms"] is not None
            ]

        def _percentile(values: list[int], p: float) -> int | None:
            if not values:
                return None
            idx = max(0, min(len(values) - 1, int(round((len(values) - 1) * p))))
            return values[idx]

        return DocsSearchTelemetryMetrics(
            window_minutes=window_minutes,
            total_queries=total_queries,
            zero_result_queries=zero_result_queries,
            zero_result_rate=(zero_result_queries / total_queries) if total_queries > 0 else 0.0,
            queries_with_click=queries_with_click,
            query_ctr=(queries_with_click / total_queries) if total_queries > 0 else 0.0,
            median_time_to_first_success_ms=_percentile(success_times, 0.50),
            p75_time_to_first_success_ms=_percentile(success_times, 0.75),
        )
