"""Shared validation constants and constrained types for Pydantic schemas."""

from __future__ import annotations

from typing import Annotated
from zoneinfo import available_timezones

from pydantic import AfterValidator

VALID_TIMEZONES: frozenset[str] = frozenset(available_timezones())


def _check_timezone(value: str) -> str:
    """``AfterValidator`` callback: ensure ``value`` is a known IANA zone name.

    Args:
        value: Candidate timezone string from the request body.

    Returns:
        The same string if valid.

    Raises:
        ValueError: If ``value`` is not in :data:`VALID_TIMEZONES`.
    """
    if value not in VALID_TIMEZONES:
        raise ValueError(
            f"Unknown timezone '{value}'. "
            "Use a valid IANA timezone (e.g. 'UTC', 'Europe/Moscow', 'America/New_York')."
        )
    return value


# Annotated alias: string must pass :func:`_check_timezone`.
TimezoneField = Annotated[str, AfterValidator(_check_timezone)]
