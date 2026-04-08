"""Idempotency helpers for write operations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class IdempotencyRecord:
    """Stored response metadata for one idempotent request key."""

    payload_hash: str
    status_code: int
    response_body: dict[str, Any]


def build_payload_hash(payload: dict[str, Any]) -> str:
    """Build deterministic hash for request payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(canonical.encode("utf-8")).hexdigest()
