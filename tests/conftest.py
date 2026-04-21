"""Pytest fixtures for API tests.

Sets a dedicated SQLite path and QA-like env before importing the app, provisions schema and
reference data once per session, and exposes a :class:`fastapi.testclient.TestClient` for HTTP tests.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# Configure test DB before importing app modules.
TEST_DB_PATH = Path(__file__).resolve().parent / "test_app.sqlite3"
os.environ["SQLITE_DB_PATH"] = str(TEST_DB_PATH)
os.environ.setdefault("APP_NAME", "ETR Study App API (tests)")
os.environ["APP_ENV"] = "qa"
os.environ.setdefault("APP_HOST", "127.0.0.1")
os.environ.setdefault("APP_PORT", "8001")
os.environ.setdefault("API_AUTH_STRATEGY", "mock_api_key")
os.environ.setdefault("API_AUTH_HEADER", "X-API-Key")
os.environ.setdefault("API_MOCK_API_KEY", "test-api-key")
os.environ.setdefault("API_RATE_LIMIT_REQUESTS", "100")
os.environ.setdefault("API_RATE_LIMIT_WINDOW_SECONDS", "60")
os.environ.setdefault("API_BODY_MAX_BYTES", "1048576")

from app.core.database import SessionLocal, engine
from app.main import app
from app.models import Base
from tests.api.v1.user_test_utils import (
    TEST_INVALIDATION_REASON_UUID,
    TEST_SYSTEM_UUID,
    TEST_SYSTEM_UUID_ALT,
)


def _seed_reference_data() -> None:
    """Insert minimal ``timezones``, ``systems``, and ``invalidation_reasons`` for user FKs.

    Replaces existing rows so tests start from a known reference set.
    """
    with SessionLocal() as session:
        session.execute(text("DELETE FROM timezones"))
        session.execute(text("DELETE FROM systems"))
        session.execute(text("DELETE FROM invalidation_reasons"))
        session.execute(
            text(
                "INSERT INTO systems (system_uuid, code, name) VALUES "
                "(:uuid, 'test-system', 'Test system')"
            ),
            {"uuid": TEST_SYSTEM_UUID},
        )
        session.execute(
            text(
                "INSERT INTO systems (system_uuid, code, name) VALUES "
                "(:uuid, 'test-system-alt', 'Test system alt')"
            ),
            {"uuid": TEST_SYSTEM_UUID_ALT},
        )
        session.execute(
            text(
                "INSERT INTO invalidation_reasons "
                "(invalidation_reason_uuid, code, description) VALUES "
                "(:uuid, 'test-ir', 'Test invalidation')"
            ),
            {"uuid": TEST_INVALIDATION_REASON_UUID},
        )
        session.execute(
            text(
                "INSERT INTO timezones (code, utc_offset) VALUES "
                "('UTC', 0), ('Europe/Moscow', 180), ('America/New_York', -300)"
            )
        )
        session.commit()


@pytest.fixture(scope="session", autouse=True)
def prepare_database() -> Iterator[None]:
    """Session-scoped: drop/create schema, seed reference data, tear down file DB.

    Yields:
        Control after setup; on teardown drops tables and removes the SQLite file.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _seed_reference_data()
    yield
    Base.metadata.drop_all(bind=engine)
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture(autouse=True)
def clean_users_table() -> None:
    """Autouse: delete dependent rows then ``users`` before each test function.

    Ensures idempotency and API tests do not leak state across cases.
    """
    with SessionLocal() as session:
        session.execute(text("DELETE FROM idempotency_keys"))
        session.execute(text("DELETE FROM users"))
        session.commit()


@pytest.fixture()
def client() -> TestClient:
    """ASGI test client with the same mock API key as ``API_MOCK_API_KEY`` in this module.

    Returns:
        :class:`fastapi.testclient.TestClient` bound to :data:`app.main.app`.
    """
    return TestClient(app, headers={"X-API-Key": "test-api-key"})
