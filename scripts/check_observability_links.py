"""Smoke-check local observability URLs for HTTP availability."""

from __future__ import annotations

import argparse
import os
import urllib.error
import urllib.parse
import urllib.request


def _probe(url: str, timeout_seconds: float) -> tuple[bool, str]:
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
    api_host = os.getenv("OBS_API_HOST", "127.0.0.1").strip() or "127.0.0.1"
    api_port = int(os.getenv("OBS_API_PORT", os.getenv("APP_PORT", "8000")))
    prom_host = os.getenv("OBS_PROM_HOST", "127.0.0.1").strip() or "127.0.0.1"
    prom_port = int(os.getenv("OBS_PROM_PORT", "9090"))
    graf_host = os.getenv("OBS_GRAF_HOST", "127.0.0.1").strip() or "127.0.0.1"
    graf_port = int(os.getenv("OBS_GRAF_PORT", "3001"))

    api_base = f"http://{api_host}:{api_port}"
    prom_base = f"http://{prom_host}:{prom_port}"
    graf_base = f"http://{graf_host}:{graf_port}"
    return [
        f"{api_base}/live",
        f"{api_base}/ready",
        f"{api_base}/metrics",
        f"{prom_base}/-/healthy",
        f"{prom_base}/targets",
        f"{prom_base}/graph?g0.expr=sum%28rate%28http_requests_total%5B1m%5D%29%29&g0.tab=0",
        f"{prom_base}/graph?g0.expr=100%20*%20sum%28rate%28http_requests_total%7Bstatus_code%3D~%225..%7C4..%22%7D%5B5m%5D%29%29%20%2F%20sum%28rate%28http_requests_total%5B5m%5D%29%29&g0.tab=0",
        f"{prom_base}/graph?g0.expr=1000%20*%20histogram_quantile%280.95%2C%20sum%28rate%28http_request_duration_seconds_bucket%5B5m%5D%29%29%20by%20%28le%29%29&g0.tab=0",
        f"{prom_base}/graph?g0.expr=1000%20*%20histogram_quantile%280.95%2C%20sum%28rate%28db_operation_duration_seconds_bucket%5B5m%5D%29%29%20by%20%28le%29%29&g0.tab=0",
        f"{graf_base}/api/health",
        f"{graf_base}/d/study-app-observability/study-app-observability?orgId=1",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check observability links.")
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.5,
        help="Timeout in seconds for each request (default: 2.5).",
    )
    parser.add_argument(
        "--url",
        dest="extra_urls",
        action="append",
        default=[],
        help="Extra URL to probe (repeatable).",
    )
    args = parser.parse_args()

    urls = _build_default_urls() + list(args.extra_urls)
    failures = 0

    for url in urls:
        _validate_url(url)
        ok, message = _probe(url, timeout_seconds=args.timeout)
        prefix = "OK" if ok else "FAIL"
        print(f"[{prefix}] {message}")
        if not ok:
            failures += 1

    if failures:
        print(f"\nObservability smoke-check failed: {failures} URL(s) failed.")
        return 1
    print("\nObservability smoke-check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
