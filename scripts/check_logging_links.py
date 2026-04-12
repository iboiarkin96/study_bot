"""Smoke-check local Elasticsearch + Kibana URLs (logging stack)."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request


def _probe(url: str, timeout_seconds: float) -> tuple[bool, str]:
    """Perform GET and treat HTTP 200 as success (Kibana /api/status returns JSON)."""
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = response.getcode()
            if status == 200:
                return True, f"200 OK ({url})"
            return False, f"{status} ({url})"
    except urllib.error.HTTPError as exc:
        return False, f"{exc.code} HTTP error ({url})"
    except urllib.error.URLError as exc:
        return False, f"unreachable: {exc.reason} ({url})"
    except TimeoutError:
        return False, f"timeout ({url})"


def _validate_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")


def _build_default_urls() -> list[str]:
    es_host = os.getenv("OBS_ES_HOST", "127.0.0.1").strip() or "127.0.0.1"
    es_port = int(os.getenv("OBS_ES_PORT", os.getenv("ELASTICSEARCH_PORT", "9200")))
    kib_host = os.getenv("OBS_KIB_HOST", "127.0.0.1").strip() or "127.0.0.1"
    kib_port = int(os.getenv("OBS_KIB_PORT", os.getenv("KIBANA_PORT", "5601")))
    es_base = f"http://{es_host}:{es_port}"
    kib_base = f"http://{kib_host}:{kib_port}"
    return [
        f"{es_base}/",
        f"{kib_base}/api/status",
    ]


def _elasticsearch_cluster_health(url_base: str, timeout_seconds: float) -> tuple[bool, str]:
    """GET _cluster/health and require status not 'red' (yellow is ok for single-node)."""
    url = f"{url_base.rstrip('/')}/_cluster/health"
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            if response.getcode() != 200:
                return False, f"{response.getcode()} ({url})"
            body = response.read().decode("utf-8")
            data = json.loads(body)
            status = data.get("status", "")
            if status == "red":
                return False, f"cluster health red ({url})"
            return True, f"cluster {status} ({url})"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return False, f"{exc} ({url})"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-check Elasticsearch + Kibana (logging stack)."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Timeout in seconds for each request (default: 5).",
    )
    parser.add_argument(
        "--url",
        dest="extra_urls",
        action="append",
        default=[],
        help="Extra URL to probe (repeatable).",
    )
    args = parser.parse_args()

    es_host = os.getenv("OBS_ES_HOST", "127.0.0.1").strip() or "127.0.0.1"
    es_port = int(os.getenv("OBS_ES_PORT", os.getenv("ELASTICSEARCH_PORT", "9200")))
    es_base = f"http://{es_host}:{es_port}"

    urls = _build_default_urls() + list(args.extra_urls)
    failures = 0

    ok, message = _elasticsearch_cluster_health(es_base, timeout_seconds=args.timeout)
    prefix = "OK" if ok else "FAIL"
    print(f"[{prefix}] {message}")
    if not ok:
        failures += 1

    for url in urls:
        _validate_url(url)
        if "/_cluster/health" in url:
            continue
        ok, message = _probe(url, timeout_seconds=args.timeout)
        prefix = "OK" if ok else "FAIL"
        print(f"[{prefix}] {message}")
        if not ok:
            failures += 1

    if failures:
        print(f"\nLogging stack smoke-check failed: {failures} check(s) failed.")
        return 1
    print("\nLogging stack smoke-check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
