"""Pytest fixtures for API tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text


# Configure test DB before importing app modules.
TEST_DB_PATH = Path(__file__).resolve().parent / "test_app.sqlite3"
os.environ["SQLITE_DB_PATH"] = str(TEST_DB_PATH)
os.environ.setdefault("APP_NAME", "Study App API (tests)")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_HOST", "127.0.0.1")
os.environ.setdefault("APP_PORT", "8001")

from app.main import app  # noqa: E402
from app.core.database import SessionLocal, engine  # noqa: E402
from app.models import Base  # noqa: E402


def _seed_reference_data() -> None:
    with SessionLocal() as session:
        session.execute(text("DELETE FROM timezones"))
        session.execute(
            text(
                "INSERT INTO timezones (code, utc_offset) VALUES "
                "('UTC', 0), ('Europe/Moscow', 180), ('America/New_York', -300)"
            )
        )
        session.commit()


@pytest.fixture(scope="session", autouse=True)
def prepare_database() -> None:
    """Create clean schema for the test session."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _seed_reference_data()
    yield
    Base.metadata.drop_all(bind=engine)
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture(autouse=True)
def clean_users_table() -> None:
    """Isolate tests by truncating users table before each test."""
    with SessionLocal() as session:
        session.execute(text("DELETE FROM users"))
        session.commit()


@pytest.fixture()
def client() -> TestClient:
    """FastAPI test client fixture."""
    return TestClient(app)

