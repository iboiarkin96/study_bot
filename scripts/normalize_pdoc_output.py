"""Post-process pdoc HTML under docs/pdoc/.

Strip unstable memory addresses from HTML and ``search.js`` (function reprs) so
``make api-docs`` output is diff-stable across machines and runs. Re-serialize the
embedded lunr ``docs`` JSON in ``search.js`` with sorted keys — pdoc otherwise emits
trie children in nondeterministic order, which breaks ``make docs-check`` drift
detection. Also ensure
every pdoc HTML document links the shared docs favicon and loads Inter.

pdoc output is otherwise left unchanged — no site chrome or ``docs-nav.js``.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_API = ROOT / "docs" / "pdoc"
DOCS_ASSETS = ROOT / "docs" / "assets"
FAVICON_NAME = "favicon.svg"

# e.g. ``<function foo at 0x10ab02c40>`` in HTML-escaped form or plain text
_AT_ADDR = re.compile(r" at 0x[0-9a-f]{8,16}")

# pdoc ``search.js`` embeds the lunr index as ``const docs = {...};``
_SEARCH_JS_MARKER = "/** pdoc search index */const docs = "


def main() -> int:
    if not DOCS_API.is_dir():
        print("docs/pdoc missing; skip pdoc normalization", file=sys.stderr)
        return 0
    changed = 0
    for path in list(DOCS_API.rglob("*.html")) + [DOCS_API / "search.js"]:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        new = _AT_ADDR.sub("", text)
        if path.name == "search.js":
            new = _canonicalize_pdoc_search_js(new)
        if path.suffix == ".html":
            new = _inject_favicon(new, path)
            new = _inject_inter_font(new)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed += 1

    if changed:
        print(f"Normalized unstable pdoc reprs in {changed} file(s) under docs/pdoc/")
    return 0


def _canonicalize_pdoc_search_js(text: str) -> str:
    """Rewrite embedded lunr index JSON with sorted keys for deterministic output."""
    idx = text.find(_SEARCH_JS_MARKER)
    if idx == -1:
        return text
    start = idx + len(_SEARCH_JS_MARKER)
    try:
        data, end_idx = json.JSONDecoder().raw_decode(text, start)
    except json.JSONDecodeError:
        return text
    serialized = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return text[:start] + serialized + text[end_idx:]


_INTER_FONT_MARKER = "fonts.googleapis.com/css2?family=Inter"
_INTER_FONT_LINKS = (
    '    <link rel="preconnect" href="https://fonts.googleapis.com"/>\n'
    '    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin=""/>\n'
    '    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&amp;display=swap"/>\n'
    "    <style>body,button,input{font-family:Inter,system-ui,-apple-system,sans-serif}</style>\n"
)


def _inject_inter_font(html: str) -> str:
    """Inject Inter font into pdoc HTML pages that don't already have it.

    pdoc ships with Bootstrap's system-font stack. This replaces it with Inter
    to match the rest of the docs site — injected into the custom.css slot so
    it loads after pdoc's own theme and wins the cascade.
    """
    if _INTER_FONT_MARKER in html or "</head>" not in html:
        return html
    return html.replace("</head>", f"{_INTER_FONT_LINKS}</head>", 1)


def _inject_favicon(html: str, html_path: Path) -> str:
    """Insert favicon ``<link>`` tag into a pdoc HTML ``<head>`` when missing.

    Args:
        html: Full HTML source.
        html_path: Absolute path to the HTML file being normalized.

    Returns:
        Possibly updated HTML with a single favicon link in ``<head>``.
    """
    if 'rel="icon"' in html or "</head>" not in html:
        return html
    favicon_path = DOCS_ASSETS / FAVICON_NAME
    rel_href = Path(os.path.relpath(favicon_path, html_path.parent)).as_posix()
    link = f'    <link rel="icon" type="image/svg+xml" href="{rel_href}"/>\n'
    return html.replace("</head>", f"{link}</head>", 1)


if __name__ == "__main__":
    raise SystemExit(main())
