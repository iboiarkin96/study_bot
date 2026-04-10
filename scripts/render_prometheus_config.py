"""Render Prometheus config from template using environment variables."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "ops" / "prometheus" / "prometheus.tpl.yml"
OUTPUT_PATH = ROOT / "ops" / "prometheus" / "prometheus.yml"


def main() -> int:
    """Read ``prometheus.tpl.yml``, substitute env-driven placeholders, write ``prometheus.yml``.

    Environment:
        PROMETHEUS_SCRAPE_TARGET: Scrape host:port for the API (default ``host.docker.internal:8000``).
        PROMETHEUS_READY_PROBE_URL: Full URL for the readiness probe used in config.

    Returns:
        Exit code ``0`` on success.

    Raises:
        ValueError: If required env values resolve to empty strings.
    """
    scrape_target = os.getenv("PROMETHEUS_SCRAPE_TARGET", "host.docker.internal:8000").strip()
    if not scrape_target:
        raise ValueError("PROMETHEUS_SCRAPE_TARGET must not be empty.")

    ready_probe_url = os.getenv(
        "PROMETHEUS_READY_PROBE_URL",
        "http://host.docker.internal:8000/ready",
    ).strip()
    if not ready_probe_url:
        raise ValueError("PROMETHEUS_READY_PROBE_URL must not be empty.")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = template.replace("${PROMETHEUS_SCRAPE_TARGET}", scrape_target)
    rendered = rendered.replace("${PROMETHEUS_READY_PROBE_URL}", ready_probe_url)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"Rendered {OUTPUT_PATH} with target {scrape_target}, ready probe {ready_probe_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
