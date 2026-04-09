"""Render Prometheus config from template using environment variables."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "ops" / "prometheus" / "prometheus.tpl.yml"
OUTPUT_PATH = ROOT / "ops" / "prometheus" / "prometheus.yml"


def main() -> int:
    scrape_target = os.getenv("PROMETHEUS_SCRAPE_TARGET", "host.docker.internal:8000").strip()
    if not scrape_target:
        raise ValueError("PROMETHEUS_SCRAPE_TARGET must not be empty.")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = template.replace("${PROMETHEUS_SCRAPE_TARGET}", scrape_target)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"Rendered {OUTPUT_PATH} with target {scrape_target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
