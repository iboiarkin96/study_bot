"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for API and database."""

    app_name: str
    app_env: str
    app_host: str
    app_port: int
    sqlite_db_path: str

    @property
    def sqlite_url(self) -> str:
        """Build SQLAlchemy URL for SQLite from configured file path."""
        db_path = Path(self.sqlite_db_path).expanduser()
        if db_path.is_absolute():
            return f"sqlite:///{db_path}"
        return f"sqlite:///{Path.cwd() / db_path}"


def get_settings() -> Settings:
    """Load validated settings from .env/environment."""
    db_path = os.getenv("SQLITE_DB_PATH", "").strip()
    if not db_path:
        raise ValueError("Missing SQLITE_DB_PATH in environment.")

    return Settings(
        app_name=os.getenv("APP_NAME", "Study App API").strip() or "Study App API",
        app_env=os.getenv("APP_ENV", "local").strip() or "local",
        app_host=os.getenv("APP_HOST", "127.0.0.1").strip() or "127.0.0.1",
        app_port=int(os.getenv("APP_PORT", "8000")),
        sqlite_db_path=db_path,
    )
