"""GET /api/v1/user/{system_uuid}/{system_user_id} — only when real ids exist in the DB.

If ROTATE_SYSTEM_USER_IDS is empty, this module does not participate in load (empty MIX).
"""

from __future__ import annotations

from app.api.v1.user import USER_HTTP_BASE_PATH
from app.openapi.examples.users import SYSTEM_UUID_EXAMPLES
from tools.load_testing.request import BuiltRequest, RunContext

GROUP = "user"

# This file's share of GROUP_WEIGHTS["user"] (with create.py must sum to 1.0).
SHARE_OF_GROUP = 0.15

# Fill with system_user_id values of existing users (from your DB).
ROTATE_SYSTEM_USER_IDS: list[str] = []


def _get_user(ctx: RunContext) -> BuiltRequest:
    """GET existing user by rotating through :data:`ROTATE_SYSTEM_USER_IDS`.

    Args:
        ctx: Load context; ``run_in_scenario`` picks the id index.

    Returns:
        Built GET request expecting 200.

    Raises:
        RuntimeError: If ``ROTATE_SYSTEM_USER_IDS`` is empty (scenario misconfigured).
    """
    if not ROTATE_SYSTEM_USER_IDS:
        raise RuntimeError("ROTATE_SYSTEM_USER_IDS is empty — fill tools/.../user/get.py")
    sid = ROTATE_SYSTEM_USER_IDS[ctx.run_in_scenario % len(ROTATE_SYSTEM_USER_IDS)]
    return BuiltRequest(
        method="GET",
        path=f"{USER_HTTP_BASE_PATH}/{SYSTEM_UUID_EXAMPLES[0]}/{sid}",
        headers={},
        json=None,
        params=None,
        expect_status=200,
    )


if ROTATE_SYSTEM_USER_IDS:
    MIX: dict[str, float] = {
        "user.get.ok": 1.0,
    }
    SCENARIOS: dict[str, object] = {
        "user.get.ok": _get_user,
    }
else:
    # Does not participate in load; create.py keeps SHARE_OF_GROUP at 1.0
    SHARE_OF_GROUP = 0.0
    MIX = {}
    SCENARIOS = {}
