"""Repository for persisted idempotency records."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.idempotency import IdempotencyRecord
from app.models.core.idempotency_key import IdempotencyKeyRecord


class IdempotencyRepository:
    """Persistence for :class:`~app.models.core.idempotency_key.IdempotencyKeyRecord` rows."""

    def __init__(self, session: Session) -> None:
        """Bind to an ORM session for idempotency storage operations.

        Args:
            session: Active SQLAlchemy session.
        """
        self.session = session

    def get(self, endpoint_path: str, idempotency_key: str) -> IdempotencyRecord | None:
        """Load a stored idempotency record for a route and key.

        Args:
            endpoint_path: Normalized path (e.g. ``/api/v1/user``).
            idempotency_key: Client-supplied idempotency token.

        Returns:
            Parsed :class:`~app.core.idempotency.IdempotencyRecord` or ``None``.
        """
        stmt = select(IdempotencyKeyRecord).where(
            IdempotencyKeyRecord.endpoint_path == endpoint_path,
            IdempotencyKeyRecord.idempotency_key == idempotency_key,
        )
        row = self.session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return IdempotencyRecord(
            payload_hash=row.payload_hash,
            status_code=row.status_code,
            response_body=json.loads(row.response_body),
        )

    def save(
        self,
        endpoint_path: str,
        idempotency_key: str,
        payload_hash: str,
        status_code: int,
        response_body: dict[str, Any],
    ) -> None:
        """Insert a new idempotency row after a successful first execution.

        Args:
            endpoint_path: Route path for the write operation.
            idempotency_key: Client idempotency token.
            payload_hash: SHA-256 of the canonical request body JSON.
            status_code: HTTP status returned to the client on first success.
            response_body: JSON-serializable response body to replay on duplicates.
        """
        row = IdempotencyKeyRecord(
            endpoint_path=endpoint_path,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            status_code=status_code,
            response_body=json.dumps(
                response_body,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
        )
        self.session.add(row)
        self.session.commit()
