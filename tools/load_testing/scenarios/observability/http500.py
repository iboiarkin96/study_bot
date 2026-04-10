"""GET /__loadtest/http500 — only when LOADTEST_HTTP_500=true on the server."""

from __future__ import annotations

from tools.load_testing.request import BuiltRequest, RunContext

GROUP = "observability_5xx"

SHARE_OF_GROUP = 1.0

MIX: dict[str, float] = {
    "observability.http500": 1.0,
}


def _http500(ctx: RunContext) -> BuiltRequest:
    """Request optional ``/__loadtest/http500`` endpoint (server must enable ``LOADTEST_HTTP_500``).

    Args:
        ctx: Load context (unused; signature fixed for scenario protocol).

    Returns:
        Built GET expecting HTTP 500 for error-rate drills.
    """
    return BuiltRequest(
        method="GET",
        path="/__loadtest/http500",
        headers={},
        json=None,
        params=None,
        expect_status=500,
    )


SCENARIOS: dict[str, object] = {
    "observability.http500": _http500,
}
