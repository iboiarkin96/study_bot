"""POST user create — success (201) and 422 via invalid fields.

Path and valid body are not duplicated: use `USER_HTTP_BASE_PATH` and `UserCreateRequest` in the app.
New scenarios: add keys to MIX and SCENARIOS (keys must be globally unique).
"""

from __future__ import annotations

from app.api.v1.user import USER_HTTP_BASE_PATH
from tools.load_testing.request import BuiltRequest, RunContext
from tools.load_testing.user_payload import apply_break_field, base_user_create

GROUP = "user"

# This file's share inside GROUP_WEIGHTS["user"]. If you add user/get.py, set e.g. 0.85 here
# and 0.15 in get.py (sums to 1.0 across user files).
SHARE_OF_GROUP = 1.0

# Scenario mix inside this file (sums to 1.0)
MIX: dict[str, float] = {
    "user.create.ok": 0.65,
    "user.create.validation_timezone": 0.20,
    "user.create.validation_full_name": 0.15,
}


def _post_user(ctx: RunContext, body: dict, expect_status: int) -> BuiltRequest:
    """POST ``USER_HTTP_BASE_PATH`` with JSON body and a unique idempotency header.

    Args:
        ctx: Request sequence context for key generation.
        body: JSON-serializable user create body.
        expect_status: Expected HTTP status for the runner assertion.

    Returns:
        :class:`~tools.load_testing.request.BuiltRequest` for the runner.
    """
    return BuiltRequest(
        method="POST",
        path=USER_HTTP_BASE_PATH,
        headers={
            "Idempotency-Key": f"load-{ctx.seq}-{ctx.nonce}",
            "Content-Type": "application/json",
        },
        json=body,
        params=None,
        expect_status=expect_status,
    )


def _ok(ctx: RunContext) -> BuiltRequest:
    """Successful create: valid body, expect 201.

    Args:
        ctx: Load context for unique ``system_user_id``.

    Returns:
        Built POST request expecting 201.
    """
    sid = f"load-{ctx.seq}-{ctx.nonce[:12]}"
    body = base_user_create(sid)
    return _post_user(ctx, body, 201)


def _bad_timezone(ctx: RunContext) -> BuiltRequest:
    """Invalid timezone field; expect HTTP 422.

    Args:
        ctx: Load context.

    Returns:
        Built POST request expecting 422.
    """
    sid = f"load-badtz-{ctx.seq}-{ctx.nonce[:12]}"
    body = apply_break_field(base_user_create(sid), "timezone")
    return _post_user(ctx, body, 422)


def _bad_full_name(ctx: RunContext) -> BuiltRequest:
    """Empty ``full_name``; expect HTTP 422.

    Args:
        ctx: Load context.

    Returns:
        Built POST request expecting 422.
    """
    sid = f"load-badfn-{ctx.seq}-{ctx.nonce[:12]}"
    body = apply_break_field(base_user_create(sid), "full_name")
    return _post_user(ctx, body, 422)


SCENARIOS: dict[str, object] = {
    "user.create.ok": _ok,
    "user.create.validation_timezone": _bad_timezone,
    "user.create.validation_full_name": _bad_full_name,
}
