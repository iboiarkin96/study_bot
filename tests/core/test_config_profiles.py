"""Configuration profile and governance tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import _normalize_app_env, get_settings


def _set_base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SQLITE_DB_PATH", str(Path("tests/test_app.sqlite3")))
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://example.com")
    monkeypatch.setenv("API_AUTH_STRATEGY", "mock_api_key")
    monkeypatch.setenv("API_MOCK_API_KEY", "secure-key-value")
    monkeypatch.setenv("METRICS_ENABLED", "true")
    monkeypatch.setenv("LOG_LEVEL", "INFO")


def test_normalize_app_env_maps_aliases() -> None:
    assert _normalize_app_env("local") == "dev"
    assert _normalize_app_env("development") == "dev"
    assert _normalize_app_env("staging") == "qa"
    assert _normalize_app_env("production") == "prod"
    assert _normalize_app_env("test") == "qa"


def test_normalize_app_env_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        _normalize_app_env("sandbox")


def test_qa_profile_rejects_disabled_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "qa")
    monkeypatch.setenv("API_AUTH_STRATEGY", "disabled")

    with pytest.raises(ValueError, match="not allowed in qa/prod"):
        get_settings()


def test_prod_profile_rejects_localhost_cors(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "http://127.0.0.1:3000")

    with pytest.raises(ValueError, match="must not contain localhost in prod"):
        get_settings()
