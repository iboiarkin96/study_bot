"""User domain ``USER_*`` stable errors and Pydantic (field, error_type) → rule maps."""

from __future__ import annotations

from app.errors.types import StableError

# --- Business (non-422) ---

USER_101 = StableError(
    "USER_101",
    "USER_CREATE_ALREADY_EXISTS",
    "User with this `system_user_id` and `system_uuid` already exists.",
)

USER_102 = StableError(
    "USER_102",
    "USER_PATCH_BODY_EMPTY",
    "PATCH body must include at least one field to update.",
)

USER_404 = StableError(
    "USER_404",
    "USER_NOT_FOUND",
    "User with this `system_user_id` and `system_uuid` was not found.",
)

# --- Validation (422) — create ---

USER_001 = StableError(
    "USER_001",
    "USER_CREATE_SYSTEM_USER_ID_REQUIRED",
    "Field `system_user_id` is required.",
)
USER_002 = StableError(
    "USER_002",
    "USER_CREATE_SYSTEM_USER_ID_INVALID",
    "Field `system_user_id` must not be empty.",
)
USER_003 = StableError(
    "USER_003",
    "USER_CREATE_FULL_NAME_REQUIRED",
    "Field `full_name` is required.",
)
USER_004 = StableError(
    "USER_004",
    "USER_CREATE_FULL_NAME_TOO_SHORT",
    "Field `full_name` must not be empty.",
)
USER_005 = StableError(
    "USER_005",
    "USER_CREATE_FULL_NAME_TOO_LONG",
    "Field `full_name` exceeds max length.",
)
USER_006 = StableError(
    "USER_006",
    "USER_CREATE_USERNAME_TOO_LONG",
    "Field `username` exceeds max length.",
)
USER_007 = StableError(
    "USER_007",
    "USER_CREATE_TIMEZONE_INVALID",
    "Field `timezone` must be a valid IANA timezone.",
)
USER_008 = StableError(
    "USER_008",
    "USER_CREATE_TIMEZONE_TOO_LONG",
    "Field `timezone` exceeds max length.",
)
USER_009 = StableError(
    "USER_009",
    "USER_CREATE_SYSTEM_UUID_INVALID",
    "Field `system_uuid` must be a valid UUID.",
)
USER_010 = StableError(
    "USER_010",
    "USER_CREATE_INVALIDATION_REASON_UUID_INVALID",
    "Field `invalidation_reason_uuid` must be a valid UUID.",
)
USER_011 = StableError(
    "USER_011",
    "USER_CREATE_IS_ROW_INVALID_TYPE",
    "Field `is_row_invalid` must be an integer.",
)
USER_012 = StableError(
    "USER_012",
    "USER_CREATE_IS_ROW_INVALID_MIN",
    "Field `is_row_invalid` must be >= 0.",
)
USER_013 = StableError(
    "USER_013",
    "USER_CREATE_IS_ROW_INVALID_MAX",
    "Field `is_row_invalid` must be <= 1.",
)
USER_025 = StableError(
    "USER_025",
    "USER_CREATE_SYSTEM_UUID_REQUIRED",
    "Field `system_uuid` is required.",
)

# --- Validation (422) — update / patch ---

USER_014 = StableError(
    "USER_014",
    "USER_UPDATE_FULL_NAME_REQUIRED",
    "Field `full_name` is required.",
)
USER_015 = StableError(
    "USER_015",
    "USER_UPDATE_FULL_NAME_TOO_SHORT",
    "Field `full_name` must not be empty.",
)
USER_016 = StableError(
    "USER_016",
    "USER_UPDATE_FULL_NAME_TOO_LONG",
    "Field `full_name` exceeds max length.",
)
USER_017 = StableError(
    "USER_017",
    "USER_UPDATE_USERNAME_TOO_LONG",
    "Field `username` exceeds max length.",
)
USER_018 = StableError(
    "USER_018",
    "USER_UPDATE_TIMEZONE_INVALID",
    "Field `timezone` must be a valid IANA timezone.",
)
USER_019 = StableError(
    "USER_019",
    "USER_UPDATE_TIMEZONE_TOO_LONG",
    "Field `timezone` exceeds max length.",
)
USER_020 = StableError(
    "USER_020",
    "USER_UPDATE_SYSTEM_UUID_INVALID",
    "Field `system_uuid` must be a valid UUID.",
)
USER_021 = StableError(
    "USER_021",
    "USER_UPDATE_INVALIDATION_REASON_UUID_INVALID",
    "Field `invalidation_reason_uuid` must be a valid UUID.",
)
USER_022 = StableError(
    "USER_022",
    "USER_UPDATE_IS_ROW_INVALID_TYPE",
    "Field `is_row_invalid` must be an integer.",
)
USER_023 = StableError(
    "USER_023",
    "USER_UPDATE_IS_ROW_INVALID_MIN",
    "Field `is_row_invalid` must be >= 0.",
)
USER_024 = StableError(
    "USER_024",
    "USER_UPDATE_IS_ROW_INVALID_MAX",
    "Field `is_row_invalid` must be <= 1.",
)

CREATE_USER_VALIDATION_RULES: dict[tuple[str, str], StableError] = {
    ("system_user_id", "missing"): USER_001,
    ("system_user_id", "string_too_short"): USER_002,
    ("full_name", "missing"): USER_003,
    ("full_name", "string_too_short"): USER_004,
    ("full_name", "string_too_long"): USER_005,
    ("username", "string_too_long"): USER_006,
    ("timezone", "value_error"): USER_007,
    ("timezone", "string_too_long"): USER_008,
    ("system_uuid", "uuid_parsing"): USER_009,
    ("invalidation_reason_uuid", "uuid_parsing"): USER_010,
    ("is_row_invalid", "int_parsing"): USER_011,
    ("is_row_invalid", "greater_than_equal"): USER_012,
    ("is_row_invalid", "less_than_equal"): USER_013,
    ("system_uuid", "missing"): USER_025,
}

UPDATE_USER_VALIDATION_RULES: dict[tuple[str, str], StableError] = {
    ("full_name", "missing"): USER_014,
    ("full_name", "string_too_short"): USER_015,
    ("full_name", "string_too_long"): USER_016,
    ("username", "string_too_long"): USER_017,
    ("timezone", "value_error"): USER_018,
    ("timezone", "string_too_long"): USER_019,
    ("system_uuid", "uuid_parsing"): USER_020,
    ("invalidation_reason_uuid", "uuid_parsing"): USER_021,
    ("is_row_invalid", "int_parsing"): USER_022,
    ("is_row_invalid", "greater_than_equal"): USER_023,
    ("is_row_invalid", "less_than_equal"): USER_024,
}
