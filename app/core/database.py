"""Database engine and session configuration.

Attributes:
    engine: Shared SQLAlchemy :class:`~sqlalchemy.engine.Engine` for SQLite
        (``check_same_thread=False`` for use with FastAPI/async).
    SessionLocal: Session factory bound to ``engine`` for request-scoped work.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.sqlite_url,
    future=True,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db_session() -> Generator[Session, None, None]:
    """Provide a SQLAlchemy :class:`~sqlalchemy.orm.Session` for one request scope.

    Yields:
        Open ORM session.

    Note:
        The session is always closed after the consumer finishes (success or error).
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
