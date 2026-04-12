"""Per-request context for logging and future distributed tracing (OpenTelemetry)."""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar, Token

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
span_id_var: ContextVar[str | None] = ContextVar("span_id", default=None)


def normalize_request_id_header(raw: str | None) -> str | None:
    """Return a safe request id from ``X-Request-Id`` or ``None`` if invalid or empty.

    Args:
        raw: Header value from the client.

    Returns:
        Stripped id when it matches allowed characters and length, else ``None``.
    """
    if not raw:
        return None
    candidate = raw.strip()
    if not candidate or len(candidate) > 128:
        return None
    if _REQUEST_ID_RE.match(candidate):
        return candidate
    return None


def new_request_id() -> str:
    """Generate a new RFC-friendly request correlation id (UUID4)."""
    return str(uuid.uuid4())


def reset_request_context(
    rid_token: Token[str | None],
    tid_token: Token[str | None] | None = None,
    sid_token: Token[str | None] | None = None,
) -> None:
    """Reset context variables after a request (call from middleware ``finally``).

    Args:
        rid_token: Token from :func:`request_id_var.set`.
        tid_token: Optional token for ``trace_id_var``.
        sid_token: Optional token for ``span_id_var``.
    """
    request_id_var.reset(rid_token)
    if tid_token is not None:
        trace_id_var.reset(tid_token)
    if sid_token is not None:
        span_id_var.reset(sid_token)
