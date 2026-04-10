#!/usr/bin/env python3
"""Smoke-test LLM API access (one short ``chat_completion`` via ``llm_client``)."""

from __future__ import annotations

import sys

import httpx
from llm_client import chat_completion, default_model, resolve_config


def main() -> int:
    api_key, base_url, _ = resolve_config()
    if not api_key:
        print(
            "Set OPENROUTER_API_KEY or OPENAI_API_KEY in .env (see env/example).", file=sys.stderr
        )
        return 1

    model = default_model(base_url)
    try:
        text = chat_completion(
            user='Reply with the single word "ok".',
            model=model,
            temperature=0.0,
            timeout=60.0,
        )
    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response is not None else 0
        body = e.response.text[:500] if e.response is not None else ""
        if status == 402:
            print(
                "llm_ping: insufficient credits (HTTP 402). Top up at "
                "https://openrouter.ai — the API key is accepted.",
                file=sys.stderr,
            )
            return 1
        print(f"llm_ping: HTTP {status} {body}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"llm_ping: {e}", file=sys.stderr)
        return 1

    print("llm_ping: OK", f"base={base_url}", f"model={model}", sep="\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
