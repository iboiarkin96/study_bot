"""User POST bodies and field corruption for expected 422 responses.

Valid bodies are built via the app Pydantic model (`UserCreateRequest`) so API field changes do
not require maintaining a parallel dict. The load runner still uses HTTP (like curl), not direct
handler calls, so metrics and middleware match real traffic.
"""

from __future__ import annotations

import copy
from typing import Any

from app.schemas.user import UserCreateRequest

# Field names always match the API schema
BREAKABLE_FIELDS: frozenset[str] = frozenset(UserCreateRequest.model_fields.keys())


def base_user_create(system_user_id: str) -> dict[str, Any]:
    """Build a minimal valid user-create JSON dict via :class:`~app.schemas.user.UserCreateRequest`.

    Args:
        system_user_id: External id used for load-test uniqueness.

    Returns:
        ``model_dump(mode="json")`` suitable as an HTTP JSON body.
    """
    return UserCreateRequest(
        system_user_id=system_user_id,
        full_name="Load Test User",
        timezone="UTC",
    ).model_dump(mode="json")


def apply_break_field(body: dict[str, Any], field: str) -> dict[str, Any]:
    """Return a deep copy of ``body`` with a single invalid value for ``field`` (expect 422).

    Args:
        body: Valid request body dict.
        field: Key in :data:`BREAKABLE_FIELDS` to corrupt.

    Returns:
        New dict with one field set to a value that fails Pydantic validation.

    Raises:
        ValueError: If ``field`` is not a known model field name.
    """
    if field not in BREAKABLE_FIELDS:
        raise ValueError(f"Unknown field to break: {field!r}. Allowed: {sorted(BREAKABLE_FIELDS)}")

    out = copy.deepcopy(body)

    if field == "system_user_id":
        out[field] = ""
    elif field == "username":
        out[field] = "x" * 300
    elif field == "full_name":
        out[field] = ""
    elif field == "timezone":
        out[field] = "Not/A/Valid/Timezone"
    elif field == "system_uuid":
        out[field] = "not-a-uuid"
    elif field == "invalidation_reason_uuid":
        out[field] = "bad"
    elif field == "is_row_invalid":
        out[field] = 9

    return out
