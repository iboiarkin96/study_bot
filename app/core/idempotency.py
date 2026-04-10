"""Idempotency helpers for write operations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class IdempotencyRecord:
    """Cached HTTP outcome for deduplicating a write with the same idempotency key.

    Attributes:
        payload_hash: SHA-256 hex digest of the canonical JSON request body.
        status_code: HTTP status that was returned on first successful execution.
        response_body: Parsed JSON body of the response to replay on duplicates.
    """

    payload_hash: str
    status_code: int
    response_body: dict[str, Any]


def build_payload_hash(payload: dict[str, Any]) -> str:
    """Compute a stable SHA-256 hex digest of the JSON-serialized payload.

    Args:
        payload: Request body as a dict (typically ``model_dump(mode="json")``).

    Returns:
        Lowercase hex digest string.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(canonical.encode("utf-8")).hexdigest()
