"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
ENV_DIR = ROOT / "env"
_ALLOWED_APP_ENVS = {"dev", "qa", "prod"}
_APP_ENV_ALIASES = {
    "local": "dev",
    "development": "dev",
    "staging": "qa",
    "stage": "qa",
    "production": "prod",
    "test": "qa",
}


def _normalize_app_env(raw: str) -> str:
    normalized = raw.strip().lower()
    normalized = _APP_ENV_ALIASES.get(normalized, normalized)
    if normalized not in _ALLOWED_APP_ENVS:
        allowed = ", ".join(sorted(_ALLOWED_APP_ENVS))
        raise ValueError(f"APP_ENV must be one of: {allowed}. Got: {raw!r}")
    return normalized


def _load_env_files() -> None:
    base_env = ROOT / ".env"
    if base_env.exists():
        load_dotenv(base_env, override=False)

    raw_app_env = os.getenv("APP_ENV", "dev")
    app_env = _normalize_app_env(raw_app_env)
    os.environ["APP_ENV"] = app_env

    profile_env = ENV_DIR / app_env
    if profile_env.is_file():
        load_dotenv(profile_env, override=True)

    explicit_env_file = os.getenv("ENV_FILE", "").strip()
    if explicit_env_file:
        explicit_path = Path(explicit_env_file).expanduser()
        if not explicit_path.is_absolute():
            explicit_path = ROOT / explicit_path
        if explicit_path.exists():
            load_dotenv(explicit_path, override=True)
        else:
            raise ValueError(f"ENV_FILE is set but file does not exist: {explicit_path}")


_load_env_files()


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for API and database."""

    app_name: str
    app_env: str
    app_host: str
    app_port: int
    sqlite_db_path: str
    log_dir: str
    log_file_name: str
    log_level: str
    cors_allow_origins: tuple[str, ...]
    cors_allow_methods: tuple[str, ...]
    cors_allow_headers: tuple[str, ...]
    cors_allow_credentials: bool
    api_body_max_bytes: int
    api_rate_limit_requests: int
    api_rate_limit_window_seconds: int
    api_auth_strategy: str
    api_mock_api_key: str
    api_auth_header: str
    api_protected_prefix: str
    metrics_enabled: bool
    metrics_path: str
    readiness_db_timeout_ms: int
    metrics_buckets_http: tuple[float, ...]
    metrics_buckets_db: tuple[float, ...]

    @property
    def sqlite_url(self) -> str:
        """Build SQLAlchemy URL for SQLite from configured file path."""
        db_path = Path(self.sqlite_db_path).expanduser()
        if db_path.is_absolute():
            return f"sqlite:///{db_path}"
        return f"sqlite:///{Path.cwd() / db_path}"


def get_settings() -> Settings:
    """Load validated settings from .env/environment."""
    app_env = _normalize_app_env(os.getenv("APP_ENV", "dev"))
    db_path = os.getenv("SQLITE_DB_PATH", "").strip()
    if not db_path:
        raise ValueError("Missing SQLITE_DB_PATH in environment.")

    def _split_csv(value: str, default: tuple[str, ...]) -> tuple[str, ...]:
        parts = tuple(item.strip() for item in value.split(",") if item.strip())
        return parts or default

    def _as_bool(value: str, default: bool) -> bool:
        normalized = value.strip().lower()
        if not normalized:
            return default
        return normalized in {"1", "true", "yes", "on"}

    def _as_buckets(value: str, default: tuple[float, ...]) -> tuple[float, ...]:
        raw = tuple(item.strip() for item in value.split(",") if item.strip())
        if not raw:
            return default
        parsed = tuple(float(item) for item in raw)
        return tuple(sorted(set(parsed)))

    settings = Settings(
        app_name=os.getenv("APP_NAME", "Study App API").strip() or "Study App API",
        app_env=app_env,
        app_host=os.getenv("APP_HOST", "127.0.0.1").strip() or "127.0.0.1",
        app_port=int(os.getenv("APP_PORT", "8000")),
        sqlite_db_path=db_path,
        log_dir=os.getenv("LOG_DIR", "logs").strip() or "logs",
        log_file_name=os.getenv("LOG_FILE_NAME", "app.log").strip() or "app.log",
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        cors_allow_origins=_split_csv(
            os.getenv("CORS_ALLOW_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000"),
            ("http://127.0.0.1:3000", "http://localhost:3000"),
        ),
        cors_allow_methods=_split_csv(
            os.getenv("CORS_ALLOW_METHODS", "GET,POST,PUT,PATCH,DELETE,OPTIONS"), ("*",)
        ),
        cors_allow_headers=_split_csv(
            os.getenv("CORS_ALLOW_HEADERS", "Authorization,Content-Type,X-API-Key"),
            ("Authorization", "Content-Type", "X-API-Key"),
        ),
        cors_allow_credentials=_as_bool(os.getenv("CORS_ALLOW_CREDENTIALS", "false"), False),
        api_body_max_bytes=max(1024, int(os.getenv("API_BODY_MAX_BYTES", "1048576"))),
        api_rate_limit_requests=max(1, int(os.getenv("API_RATE_LIMIT_REQUESTS", "60"))),
        api_rate_limit_window_seconds=max(1, int(os.getenv("API_RATE_LIMIT_WINDOW_SECONDS", "60"))),
        api_auth_strategy=os.getenv("API_AUTH_STRATEGY", "mock_api_key").strip() or "mock_api_key",
        api_mock_api_key=os.getenv("API_MOCK_API_KEY", "local-dev-key").strip() or "local-dev-key",
        api_auth_header=os.getenv("API_AUTH_HEADER", "X-API-Key").strip() or "X-API-Key",
        api_protected_prefix=os.getenv("API_PROTECTED_PREFIX", "/api/v1").strip() or "/api/v1",
        metrics_enabled=_as_bool(os.getenv("METRICS_ENABLED", "true"), True),
        metrics_path=os.getenv("METRICS_PATH", "/metrics").strip() or "/metrics",
        readiness_db_timeout_ms=max(50, int(os.getenv("READINESS_DB_TIMEOUT_MS", "250"))),
        metrics_buckets_http=_as_buckets(
            os.getenv("METRICS_BUCKETS_HTTP", "0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2.5,5"),
            (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
        ),
        metrics_buckets_db=_as_buckets(
            os.getenv("METRICS_BUCKETS_DB", "0.001,0.0025,0.005,0.01,0.025,0.05,0.1,0.25"),
            (0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25),
        ),
    )

    if settings.app_env in {"qa", "prod"}:
        if settings.api_auth_strategy == "disabled":
            raise ValueError("API_AUTH_STRATEGY=disabled is not allowed in qa/prod.")
        if settings.api_mock_api_key == "local-dev-key":
            raise ValueError("Set a non-default API_MOCK_API_KEY for qa/prod.")
        if not settings.metrics_enabled:
            raise ValueError("METRICS_ENABLED must be true in qa/prod.")

    if settings.app_env == "prod":
        localhost_markers = ("localhost", "127.0.0.1")
        if any(
            marker in origin
            for origin in settings.cors_allow_origins
            for marker in localhost_markers
        ):
            raise ValueError("CORS_ALLOW_ORIGINS must not contain localhost in prod.")
        if settings.log_level == "DEBUG":
            raise ValueError("LOG_LEVEL=DEBUG is not allowed in prod.")

    return settings
