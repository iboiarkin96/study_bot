#!/usr/bin/env python3
"""Query local Elasticsearch for study-app logs (debug Kibana / Filebeat without UI).

Usage:
  python scripts/check_es_request_id.py
  python scripts/check_es_request_id.py 58c7fb82-6c17-4f6e-b24b-776a06d84334

Env: OBS_ES_HOST (default 127.0.0.1), OBS_ES_PORT (default 9200).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def _get(url: str, timeout: float = 10.0) -> str:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def _post(url: str, body: dict, timeout: float = 15.0) -> str:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def main() -> int:
    host = os.getenv("OBS_ES_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("OBS_ES_PORT", os.getenv("ELASTICSEARCH_PORT", "9200")))
    base = f"http://{host}:{port}"
    uuid = (sys.argv[1] if len(sys.argv) > 1 else "").strip()

    print(f"→ Elasticsearch: {base}\n")

    try:
        indices = _get(f"{base}/_cat/indices/*study-app*?v&s=index")
    except urllib.error.URLError as exc:
        print(f"✗ Cannot reach Elasticsearch: {exc}")
        print("  Start the stack: make logging-up")
        return 1

    print("Indices matching *study-app*:")
    print(indices if indices.strip() else "(none)")
    print()

    if not uuid:
        q = {
            "query": {"query_string": {"query": "*"}},
            "size": 5,
            "sort": [{"@timestamp": {"order": "desc"}}],
        }
        try:
            out = _post(f"{base}/*study-app-logs*/_search?pretty", q)
        except urllib.error.HTTPError as exc:
            print(
                f"Sample search failed: {exc.code}\n{exc.read().decode('utf-8', errors='replace')}"
            )
            return 1
        print("Last 5 documents (any) in *study-app-logs*:")
        print(out[:12000])
        print("\nPass a UUID as the first argument to search request_id / message.")
        return 0

    query = {
        "query": {"query_string": {"query": uuid}},
        "size": 10,
        "sort": [{"@timestamp": {"order": "desc"}}],
    }
    try:
        out = _post(f"{base}/*study-app-logs*/_search?pretty", query)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        print(f"✗ Search failed: {exc.code}\n{body}")
        return 1

    data = json.loads(out)
    total = data.get("hits", {}).get("total", {})
    n = total.get("value", total) if isinstance(total, dict) else total
    print(f"Hits for UUID (request_id or message): {n}\n")
    print(out[:12000])
    if n == 0:
        print(
            "\n---\n"
            "0 hits but app.log has JSON lines? Try:\n"
            "  • Kibana data view index pattern: *study-app-logs* (wildcards both sides).\n"
            "  • Time range in Discover: Last 24 hours, timezone UTC vs local.\n"
            "  • Mixed app.log (old text + new JSON): mv logs/app.log logs/app.log.bak && "
            "restart API (LOG_FORMAT=json), then: "
            "docker compose -f docker-compose.logging.yml restart filebeat\n"
            "  • docker logs study-app-filebeat — look for parsing errors.\n"
            "---"
        )
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
