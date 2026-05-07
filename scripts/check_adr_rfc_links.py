#!/usr/bin/env python3
"""Validate cross-references in `docs/adr/*.html` and `docs/rfc/*.html`.

Three strict checks (any failure exits with status 1):
    1. Every relative `href`/`src` resolves to an existing file on disk.
    2. Every in-page anchor (`href="#foo"`) matches an `id="foo"` in the same page.
    3. Every cross-doc anchor (`href="path.html#foo"`) matches an `id="foo"` in the target.

Skipped: external schemes (http/https/mailto/etc.), empty hrefs, fragments inside
`<code>`/`<pre>`/HTML comments. Anchor lookup is case-sensitive (HTML id attribute is).

Pre-commit usage: invoke without arguments. Exit code 1 blocks the commit.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parent.parent
DOCS = ROOT / "docs"
ADR = DOCS / "adr"
RFC = DOCS / "rfc"

HREF_RE = re.compile(r'(?:href|src)\s*=\s*"([^"]+)"', re.IGNORECASE)
ID_RE = re.compile(r'\bid\s*=\s*"([^"]+)"', re.IGNORECASE)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
CODE_RE = re.compile(r"<(code|pre)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)

EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "javascript:", "data:", "tel:")


def collect_pages() -> list[Path]:
    return sorted([*ADR.rglob("*.html"), *RFC.rglob("*.html")])


def is_external(target: str) -> bool:
    if not target:
        return True
    return target.startswith(EXTERNAL_PREFIXES)


def split_target(target: str) -> tuple[str, str]:
    """Return (path, anchor). Either may be empty."""
    target = target.split("?", 1)[0]
    if "#" in target:
        path, _, anchor = target.partition("#")
    else:
        path, anchor = target, ""
    return unquote(path), anchor


def find_line(content: str, idx: int) -> int:
    return content.count("\n", 0, idx) + 1


def strip_noise(text: str) -> str:
    """Blank out comments and `<code>`/`<pre>` bodies; preserve newlines for line numbers."""

    def blank(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    text = COMMENT_RE.sub(blank, text)
    text = CODE_RE.sub(blank, text)
    return text


def collect_ids(page: Path, cache: dict[Path, set[str]]) -> set[str]:
    if page not in cache:
        try:
            raw = page.read_text(encoding="utf-8", errors="replace")
        except OSError:
            cache[page] = set()
            return cache[page]
        cache[page] = set(ID_RE.findall(raw))
    return cache[page]


def scan_page(
    page: Path,
    id_cache: dict[Path, set[str]],
) -> tuple[list[dict], list[dict], list[dict]]:
    raw = page.read_text(encoding="utf-8", errors="replace")
    text = strip_noise(raw)
    page_dir = page.parent
    rel_page = str(page.relative_to(ROOT))

    own_ids = collect_ids(page, id_cache)

    broken_files: list[dict] = []
    broken_in_anchors: list[dict] = []
    broken_cross_anchors: list[dict] = []

    for m in HREF_RE.finditer(text):
        href = m.group(1).strip()
        if is_external(href):
            continue
        path_part, anchor = split_target(href)
        line = find_line(text, m.start())

        # Pure in-page anchor: only check id presence in same page.
        if not path_part:
            if not anchor:
                continue
            if anchor not in own_ids:
                broken_in_anchors.append(
                    {"page": rel_page, "href": href, "anchor": anchor, "line": line}
                )
            continue

        # File reference: resolve and check existence.
        resolved = (page_dir / path_part).resolve()
        if not resolved.exists():
            try:
                shown = str(resolved.relative_to(ROOT))
            except ValueError:
                shown = str(resolved)
            broken_files.append({"page": rel_page, "href": href, "resolved": shown, "line": line})
            continue

        # Cross-doc anchor: target exists, check anchor presence inside it.
        if anchor and resolved.is_file() and resolved.suffix.lower() == ".html":
            target_ids = collect_ids(resolved, id_cache)
            if anchor not in target_ids:
                try:
                    shown_target = str(resolved.relative_to(ROOT))
                except ValueError:
                    shown_target = str(resolved)
                broken_cross_anchors.append(
                    {
                        "page": rel_page,
                        "href": href,
                        "target": shown_target,
                        "anchor": anchor,
                        "line": line,
                    }
                )

    return broken_files, broken_in_anchors, broken_cross_anchors


def hr(label: str) -> None:
    print("─" * 78)
    print(label)
    print("─" * 78)


def _print_grouped(items: list[dict], formatter) -> None:
    current_page = ""
    for it in items:
        if it["page"] != current_page:
            current_page = it["page"]
            print(f"\n  {current_page}")
        formatter(it)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate ADR/RFC cross-references and anchors.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print nothing on success (still exits 1 on failure).",
    )
    args = parser.parse_args(argv)

    if not ADR.exists() or not RFC.exists():
        print(f"adr/rfc directory missing: {ADR} / {RFC}", file=sys.stderr)
        return 1

    pages = collect_pages()
    id_cache: dict[Path, set[str]] = {}

    broken_files: list[dict] = []
    broken_in_anchors: list[dict] = []
    broken_cross_anchors: list[dict] = []
    for p in pages:
        bf, bi, bc = scan_page(p, id_cache)
        broken_files.extend(bf)
        broken_in_anchors.extend(bi)
        broken_cross_anchors.extend(bc)

    failures = (
        (1 if broken_files else 0)
        + (1 if broken_in_anchors else 0)
        + (1 if broken_cross_anchors else 0)
    )

    if failures or not args.quiet:
        print("=" * 78)
        print("ADR / RFC LINK CHECK")
        print("=" * 78)
        print(f"\nPages scanned: {len(pages)} (ADR + RFC)\n")

        hr("1. BROKEN FILE REFERENCES (href/src → missing file)")
        if broken_files:
            _print_grouped(
                broken_files,
                lambda it: (
                    print(f"    line {it['line']:>4}  href={it['href']!r}"),
                    print(f"              → {it['resolved']} (missing)"),
                ),
            )
            print(f"\n  TOTAL: {len(broken_files)}")
        else:
            print("\n  ✓ All file references resolve.")

        print()
        hr('2. BROKEN IN-PAGE ANCHORS (href="#id" → no matching id in same page)')
        if broken_in_anchors:
            _print_grouped(
                broken_in_anchors,
                lambda it: print(
                    f"    line {it['line']:>4}  href={it['href']!r}  (no id={it['anchor']!r})"
                ),
            )
            print(f"\n  TOTAL: {len(broken_in_anchors)}")
        else:
            print("\n  ✓ All in-page anchors resolve.")

        print()
        hr('3. BROKEN CROSS-DOC ANCHORS (href="file.html#id" → no id in target)')
        if broken_cross_anchors:
            _print_grouped(
                broken_cross_anchors,
                lambda it: (
                    print(f"    line {it['line']:>4}  href={it['href']!r}"),
                    print(f"              → {it['target']} (no id={it['anchor']!r})"),
                ),
            )
            print(f"\n  TOTAL: {len(broken_cross_anchors)}")
        else:
            print("\n  ✓ All cross-doc anchors resolve.")

    if failures:
        print(
            f"\nFAILED: {failures} category(ies) reported issues — see above.",
            file=sys.stderr,
        )
        return 1
    if not args.quiet:
        print("\n✓ All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
