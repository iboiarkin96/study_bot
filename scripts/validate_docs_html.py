"""Validate HTML consistency for docs pages."""

from __future__ import annotations

from pathlib import Path

import html5lib

ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = ROOT / "docs"


def _iter_html_files() -> list[Path]:
    """Return all HTML files under docs/."""
    return sorted(DOCS_ROOT.glob("**/*.html"))


def main() -> None:
    """Validate docs HTML and fail on parser errors or known bad patterns."""
    parser = html5lib.HTMLParser(tree=html5lib.getTreeBuilder("etree"))
    errors: list[str] = []

    for html_path in _iter_html_files():
        rel = html_path.relative_to(ROOT)
        text = html_path.read_text(encoding="utf-8")

        # Guard against a known invalid pattern from earlier regressions.
        if "</wbr>" in text:
            errors.append(f"{rel}: contains invalid closing </wbr> tag")

        parser.errors.clear()
        parser.parse(text)
        if parser.errors:
            first = parser.errors[0]
            errors.append(f"{rel}: html5 parse error {first}")

    if errors:
        print("Docs HTML validation failed:")
        for item in errors:
            print(f" - {item}")
        raise SystemExit(1)

    print("Docs HTML validation passed")


if __name__ == "__main__":
    main()
