"""Shared shape for stable API error identities (code, key, message)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StableError:
    """One published error identity: stable ``code`` + ``key`` + default English ``message``."""

    code: str
    key: str
    message: str

    def as_detail(self, source: str, *, message: str | None = None) -> dict[str, str]:
        """Build the JSON ``detail`` object for HTTP error responses.

        Args:
            source: Contract layer (``validation``, ``business``, ``security``).
            message: Optional override; defaults to :attr:`message`.
        """
        return {
            "code": self.code,
            "key": self.key,
            "message": self.message if message is None else message,
            "source": source,
        }
