"""Request value types shared by load-testing scenarios and the runner."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeAlias

JsonBody: TypeAlias = dict[str, Any] | None


@dataclass
class RunContext:
    """Per-request context passed to scenario builder callables.

    Attributes:
        seq: Global request index in the run (0 .. total_requests - 1).
        run_in_scenario: How many times this scenario has been chosen in the run.
        nonce: Unique string per request (idempotency keys, synthetic user ids).
    """

    seq: int
    run_in_scenario: int
    nonce: str


@dataclass(frozen=True)
class BuiltRequest:
    """HTTP request template consumed by the load runner (relative to ``LOAD_TEST_BASE_URL``).

    Attributes:
        method: HTTP method (e.g. ``GET``, ``POST``).
        path: Path starting with ``/``, relative to base URL (e.g. ``/api/v1/user``).
        headers: Header map (e.g. ``Idempotency-Key``, ``Content-Type``).
        json: Optional JSON body dict for ``httpx``; ``None`` for no body.
        params: Optional query string parameters.
        expect_status: Expected HTTP status for assertion/logging.
    """

    method: str
    path: str
    headers: dict[str, str]
    json: JsonBody
    params: dict[str, str] | None
    expect_status: int


ScenarioBuild: TypeAlias = Callable[[RunContext], BuiltRequest]
