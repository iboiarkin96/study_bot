"""Repository for persisted idempotency records."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.idempotency import IdempotencyRecord
from app.models.core.idempotency_key import IdempotencyKeyRecord


class IdempotencyRepository:
    """Data access for idempotency key records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, endpoint_path: str, idempotency_key: str) -> IdempotencyRecord | None:
        """Fetch idempotency record by endpoint and key."""
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
        """Persist idempotency record."""
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
