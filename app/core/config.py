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
    """Map ``APP_ENV`` aliases to canonical values and validate allowed names.

    Args:
        raw: Raw value from ``APP_ENV`` (may include aliases like ``staging`` → ``qa``).

    Returns:
        Canonical environment name: ``dev``, ``qa``, or ``prod``.

    Raises:
        ValueError: If the value is not allowed after alias resolution.
    """
    normalized = raw.strip().lower()
    normalized = _APP_ENV_ALIASES.get(normalized, normalized)
    if normalized not in _ALLOWED_APP_ENVS:
        allowed = ", ".join(sorted(_ALLOWED_APP_ENVS))
        raise ValueError(f"APP_ENV must be one of: {allowed}. Got: {raw!r}")
    return normalized


def _normalize_log_format(raw: str) -> str:
    """Normalize ``LOG_FORMAT`` to ``text`` or ``json``.

    Args:
        raw: Environment string (``text``, ``json``, ``ndjson``, etc.).

    Returns:
        ``text`` or ``json``.

    Raises:
        ValueError: If the value is not recognized.
    """
    normalized = raw.strip().lower()
    if not normalized:
        return "text"
    if normalized in ("text", "plain"):
        return "text"
    if normalized in ("json", "ndjson", "jsonl"):
        return "json"
    raise ValueError(f"LOG_FORMAT must be 'text' or 'json'. Got: {raw!r}")


# Variables already set in the environment before import (e.g. `export` before uvicorn)
# must not be overwritten by `env/<APP_ENV>` — otherwise local load-testing script loses
# API_RATE_LIMIT_REQUESTS_LOADTEST when env/dev sets 60 again.
_PARENT_WINS_KEYS = (
    "API_RATE_LIMIT_REQUESTS",
    "API_RATE_LIMIT_WINDOW_SECONDS",
)


def _load_env_files() -> None:
    """Load dotenv files in order: root ``.env``, ``env/<APP_ENV>``, optional ``ENV_FILE``.

    Preserves rate-limit overrides from the parent environment for keys in
    ``_PARENT_WINS_KEYS`` when profile files are applied.

    Raises:
        ValueError: If ``ENV_FILE`` is set but the path does not exist.
    """
    parent_wins = {k: os.environ[k] for k in _PARENT_WINS_KEYS if k in os.environ}

    base_env = ROOT / ".env"
    if base_env.exists():
        load_dotenv(base_env, override=False)

    raw_app_env = os.getenv("APP_ENV", "dev")
    app_env = _normalize_app_env(raw_app_env)
    os.environ["APP_ENV"] = app_env

    profile_env = ENV_DIR / app_env
    if profile_env.is_file():
        load_dotenv(profile_env, override=True)

    for key, value in parent_wins.items():
        os.environ[key] = value

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
    """Immutable API and infrastructure settings sourced from environment variables.

    Attributes:
        app_name: Human-readable service title.
        app_env: Deployment profile: ``dev``, ``qa``, or ``prod``.
        app_host: Bind address for the HTTP server.
        app_port: Bind port for the HTTP server.
        sqlite_db_path: Path to the SQLite database file (relative or absolute).
        log_dir: Directory for rotating application log files.
        log_file_name: Log file basename inside ``log_dir``.
        log_level: Root logging level (e.g. ``INFO``, ``DEBUG``).
        log_format: ``text`` (human-readable) or ``json`` (NDJSON for log platforms).
        log_service_name: Stable service identifier in JSON logs (``service`` field).
        cors_allow_origins: Allowed CORS origin URLs.
        cors_allow_methods: Allowed CORS HTTP methods (or ``*``).
        cors_allow_headers: Allowed CORS request header names.
        cors_expose_headers: Response header names browsers may read on cross-origin responses.
        cors_allow_credentials: Whether browsers may send credentials on CORS requests.
        api_body_max_bytes: Maximum accepted HTTP request body size in bytes.
        api_rate_limit_requests: Request cap per client identifier per window for protected routes.
        api_rate_limit_window_seconds: Duration of the rate-limit window in seconds.
        api_auth_strategy: Authentication strategy identifier (e.g. ``mock_api_key``).
        api_mock_api_key: Expected secret when using the mock API key strategy.
        api_auth_header: HTTP header name that carries the API key.
        api_protected_prefix: URL path prefix that requires authentication and rate limiting.
        metrics_enabled: Whether Prometheus metrics collection and ``/metrics`` are enabled.
        metrics_path: HTTP path exposing Prometheus text exposition.
        readiness_db_timeout_ms: Maximum acceptable database ping duration for readiness.
        metrics_buckets_http: Histogram bucket upper bounds (seconds) for HTTP latency.
        metrics_buckets_db: Histogram bucket upper bounds (seconds) for DB operation latency.
    """

    app_name: str
    app_env: str
    app_host: str
    app_port: int
    sqlite_db_path: str
    log_dir: str
    log_file_name: str
    log_level: str
    log_format: str
    log_service_name: str
    cors_allow_origins: tuple[str, ...]
    cors_allow_methods: tuple[str, ...]
    cors_allow_headers: tuple[str, ...]
    cors_expose_headers: tuple[str, ...]
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
        """SQLAlchemy connection URL for the configured SQLite file.

        Returns:
            URL string of the form ``sqlite:///...`` with absolute or cwd-relative path.
        """
        db_path = Path(self.sqlite_db_path).expanduser()
        if db_path.is_absolute():
            return f"sqlite:///{db_path}"
        return f"sqlite:///{Path.cwd() / db_path}"


def get_settings() -> Settings:
    """Build a validated :class:`Settings` instance from the current process environment.

    Returns:
        Frozen settings snapshot.

    Raises:
        ValueError: If ``SQLITE_DB_PATH`` is missing, ``qa``/``prod`` invariants fail,
            or ``prod`` forbids localhost CORS / ``DEBUG`` logging.
    """
    app_env = _normalize_app_env(os.getenv("APP_ENV", "dev"))
    db_path = os.getenv("SQLITE_DB_PATH", "").strip()
    if not db_path:
        raise ValueError("Missing SQLITE_DB_PATH in environment.")

    def _split_csv(value: str, default: tuple[str, ...]) -> tuple[str, ...]:
        """Parse a comma-separated env value into stripped non-empty parts.

        Args:
            value: Raw string (often from ``os.getenv``).
            default: Used when ``value`` yields no tokens.

        Returns:
            Tuple of segment strings, or ``default`` if empty.
        """
        parts = tuple(item.strip() for item in value.split(",") if item.strip())
        return parts or default

    def _as_bool(value: str, default: bool) -> bool:
        """Parse truthy strings; empty string falls back to ``default``.

        Args:
            value: Raw string from environment.
            default: Result when ``value`` is blank.

        Returns:
            ``True`` for ``1``/``true``/``yes``/``on`` (case-insensitive), else ``False``
            when non-empty, else ``default``.
        """
        normalized = value.strip().lower()
        if not normalized:
            return default
        return normalized in {"1", "true", "yes", "on"}

    def _as_buckets(value: str, default: tuple[float, ...]) -> tuple[float, ...]:
        """Parse histogram bucket list from CSV floats; deduplicate and sort ascending.

        Args:
            value: Comma-separated float literals.
            default: Used when ``value`` is empty.

        Returns:
            Sorted unique bucket upper bounds.
        """
        raw = tuple(item.strip() for item in value.split(",") if item.strip())
        if not raw:
            return default
        parsed = tuple(float(item) for item in raw)
        return tuple(sorted(set(parsed)))

    settings = Settings(
        app_name=os.getenv("APP_NAME", "ETR Study App API").strip() or "ETR Study App API",
        app_env=app_env,
        app_host=os.getenv("APP_HOST", "127.0.0.1").strip() or "127.0.0.1",
        app_port=int(os.getenv("APP_PORT", "8000")),
        sqlite_db_path=db_path,
        log_dir=os.getenv("LOG_DIR", "logs").strip() or "logs",
        log_file_name=os.getenv("LOG_FILE_NAME", "app.log").strip() or "app.log",
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        log_format=_normalize_log_format(os.getenv("LOG_FORMAT", "json")),
        log_service_name=os.getenv("LOG_SERVICE_NAME", "study-app-api").strip() or "study-app-api",
        cors_allow_origins=_split_csv(
            os.getenv("CORS_ALLOW_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000"),
            ("http://127.0.0.1:3000", "http://localhost:3000"),
        ),
        cors_allow_methods=_split_csv(
            os.getenv("CORS_ALLOW_METHODS", "GET,POST,PUT,PATCH,DELETE,OPTIONS"), ("*",)
        ),
        cors_allow_headers=_split_csv(
            os.getenv(
                "CORS_ALLOW_HEADERS",
                "Authorization,Content-Type,X-API-Key,Idempotency-Key,X-Request-Id",
            ),
            ("Authorization", "Content-Type", "X-API-Key", "Idempotency-Key", "X-Request-Id"),
        ),
        cors_expose_headers=_split_csv(
            os.getenv(
                "CORS_EXPOSE_HEADERS",
                "X-Request-Id,X-RateLimit-Limit,X-RateLimit-Remaining,Retry-After",
            ),
            (
                "X-Request-Id",
                "X-RateLimit-Limit",
                "X-RateLimit-Remaining",
                "Retry-After",
            ),
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
