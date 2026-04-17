"""Inject a shared favicon link into docs HTML pages when missing."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = ROOT / "docs"
FAVICON_PATH = DOCS_ROOT / "assets" / "favicon.svg"


def _inject_favicon(html: str, html_path: Path) -> str:
    """Insert favicon link into ``<head>`` when the page does not have one.

    Args:
        html: Current HTML file content.
        html_path: Absolute path to the HTML file being processed.

    Returns:
        Updated HTML with favicon link in ``<head>`` when applicable.
    """
    if 'rel="icon"' in html or "</head>" not in html:
        return html
    href = Path(os.path.relpath(FAVICON_PATH, html_path.parent)).as_posix()
    link = f'  <link rel="icon" type="image/svg+xml" href="{href}" />\n'
    return html.replace("</head>", f"{link}</head>", 1)


def main() -> int:
    """Inject favicon links in docs HTML files and print update count."""
    if not DOCS_ROOT.is_dir():
        print("docs/ directory is missing; nothing to do")
        return 0

    updated = 0
    for html_path in sorted(DOCS_ROOT.rglob("*.html")):
        original = html_path.read_text(encoding="utf-8")
        patched = _inject_favicon(original, html_path)
        if patched != original:
            html_path.write_text(patched, encoding="utf-8")
            updated += 1

    print(f"Injected favicon into {updated} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
