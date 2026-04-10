"""OpenAI-compatible chat API helper.

1. ``resolve_config`` — API key, base URL, optional OpenRouter headers (from env / root ``.env``).
2. ``chat_completion`` — non-streaming chat; pass ``system`` + ``user`` (your aggregated payload).

Used by ``changelog_draft.py`` and ``llm_ping.py``. See ``env/example``.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    base = _repo_root() / ".env"
    if base.exists():
        load_dotenv(base, override=False)


def _openrouter_headers() -> dict[str, str]:
    referer = os.environ.get("OPENROUTER_HTTP_REFERER", "http://127.0.0.1:3000").strip()
    title = os.environ.get("OPENROUTER_APP_TITLE", "study_app").strip()
    return {"HTTP-Referer": referer, "X-Title": title}


def resolve_config() -> tuple[str, str, dict[str, str]]:
    """Return ``(api_key, base_url, extra_headers)`` for the configured provider."""
    load_dotenv_if_available()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    api_key = openai_key or or_key
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    if not base_url:
        base_url = (
            "https://openrouter.ai/api/v1"
            if or_key and not openai_key
            else "https://api.openai.com/v1"
        )
    extra: dict[str, str] = {}
    if "openrouter.ai" in base_url:
        extra.update(_openrouter_headers())
    return api_key, base_url, extra


def default_model(base_url: str) -> str:
    env_model = os.environ.get("OPENAI_MODEL", "").strip()
    if env_model:
        return env_model
    if "openrouter.ai" in base_url:
        return "openrouter/free"
    return "gpt-4o-mini"


def _strip_reasoning_noise(text: str) -> str:
    text = re.sub(r"<think>[\s\S]*?</think>", "", text)
    return text.strip()


def chat_completion(
    *,
    user: str,
    system: str | None = None,
    model: str | None = None,
    temperature: float = 0.3,
    timeout: float = 120.0,
) -> str:
    """Send messages; return assistant text (non-streaming)."""
    api_key, base_url, extra_headers = resolve_config()
    if not api_key:
        raise ValueError("Set OPENROUTER_API_KEY or OPENAI_API_KEY (see env/example).")

    m = model or default_model(base_url)
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    import httpx

    url = base_url.rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {
        "model": m,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        **extra_headers,
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    try:
        raw = data["choices"][0]["message"]["content"]
        if raw is None:
            raw = ""
        return _strip_reasoning_noise(raw.strip())
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Unexpected API response: {json.dumps(data)[:500]}") from e
