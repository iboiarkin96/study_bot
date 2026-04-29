#!/usr/bin/env python3
"""Audit `docs/internal/front/` for broken references and undocumented assets.

Three strict checks (any failure exits with status 1):
    1. Every `href`/`src` in every front page resolves to an existing file.
    2. Every `path: "..."` entry in `docs/assets/internal-sidebar.js` exists on disk.
    3. Every filename mentioned in prose (outside `<code>`/`<pre>`/comments) exists somewhere reachable.

Two informational reports (printed only with `--coverage`, never fail):
    4. Asset coverage — how many front pages mention each `docs/assets/*.{js,css}` file.
    5. Page size distribution — to spot overgrown vs thin pages.

Pre-commit usage: invoke without arguments. Exit code 1 blocks the commit.
Local development: `python3 scripts/audit_front_docs_links.py --coverage` for the full picture.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

# Resolve project root from the script's own location so this works in any checkout.
SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parent.parent
DOCS = ROOT / "docs"
FRONT = DOCS / "internal" / "front"
ASSETS = DOCS / "assets"

HREF_RE = re.compile(r'(?:href|src)\s*=\s*"([^"]+)"', re.IGNORECASE)
ASSET_FILE_RE = re.compile(r"[A-Za-z0-9_./-]+\.(?:js|css|html|svg|json|png|jpg|jpeg|gif|webp)")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
CODE_RE = re.compile(r"<(code|pre)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
SIDEBAR_PATH_RE = re.compile(r'path:\s*"([^"]+)"')

EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "javascript:", "data:", "tel:")


def collect_pages() -> list[Path]:
    return sorted(FRONT.rglob("*.html"))


def is_external_or_anchor(target: str) -> bool:
    if not target:
        return True
    if target.startswith("#"):
        return True
    return target.startswith(EXTERNAL_PREFIXES)


def strip_anchor_query(target: str) -> str:
    target = target.split("#", 1)[0]
    target = target.split("?", 1)[0]
    return unquote(target)


def find_line(content: str, idx: int) -> int:
    return content.count("\n", 0, idx) + 1


def strip_noise(text: str) -> str:
    """Replace HTML comments and `<code>`/`<pre>` bodies with whitespace.

    Same length so reported line numbers still map to source.
    """

    def blank(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    text = COMMENT_RE.sub(blank, text)
    text = CODE_RE.sub(blank, text)
    return text


def scan_links(page: Path) -> list[dict]:
    raw = page.read_text(encoding="utf-8", errors="replace")
    text = strip_noise(raw)
    issues: list[dict] = []
    page_dir = page.parent

    for m in HREF_RE.finditer(text):
        href = m.group(1).strip()
        if is_external_or_anchor(href):
            continue
        target_path = strip_anchor_query(href)
        if not target_path:
            continue
        resolved = (page_dir / target_path).resolve()
        if resolved.exists():
            continue
        try:
            shown = str(resolved.relative_to(ROOT))
        except ValueError:
            shown = str(resolved)
        issues.append(
            {
                "page": str(page.relative_to(ROOT)),
                "href": href,
                "resolved": shown,
                "line": find_line(text, m.start()),
            }
        )
    return issues


def scan_prose_mentions(page: Path) -> list[dict]:
    raw = page.read_text(encoding="utf-8", errors="replace")
    text = strip_noise(raw)
    issues: list[dict] = []
    seen: set[str] = set()

    for m in ASSET_FILE_RE.finditer(text):
        token = m.group(0)
        if token in seen:
            continue
        seen.add(token)
        # Skip path-shaped mentions — already covered by href scan.
        if "/" in token:
            continue
        # Accept any reachable location.
        candidates = [
            ASSETS / token,
            ROOT / "scripts" / token,
            page.parent / token,
            DOCS / token,
        ]
        if any(c.exists() for c in candidates):
            continue
        if list(DOCS.rglob(token)):
            continue
        issues.append(
            {
                "page": str(page.relative_to(ROOT)),
                "mention": token,
                "line": find_line(text, m.start()),
            }
        )
    return issues


def sidebar_paths_check() -> list[str]:
    sidebar = ASSETS / "internal-sidebar.js"
    if not sidebar.exists():
        return ["internal-sidebar.js NOT FOUND"]
    text = sidebar.read_text(encoding="utf-8")
    return [p for p in SIDEBAR_PATH_RE.findall(text) if not (DOCS / p).exists()]


def asset_coverage() -> dict:
    pages = collect_pages()
    bodies = {p: p.read_text(encoding="utf-8", errors="replace") for p in pages}
    coverage: dict[str, dict] = {}
    for asset in sorted(ASSETS.iterdir()):
        if asset.suffix not in (".js", ".css"):
            continue
        name = asset.name
        mentions: list[tuple[str, int]] = [
            (str(p.relative_to(ROOT)), body.count(name))
            for p, body in bodies.items()
            if body.count(name)
        ]
        coverage[name] = {
            "size": asset.stat().st_size,
            "total_mentions": sum(c for _, c in mentions),
            "pages": mentions,
        }
    return coverage


def page_sizes() -> list[tuple[Path, int, int]]:
    out = []
    for p in collect_pages():
        lines = p.read_text(encoding="utf-8", errors="replace").count("\n") + 1
        out.append((p.relative_to(ROOT), lines, p.stat().st_size))
    return sorted(out, key=lambda t: -t[1])


def hr(label: str) -> None:
    print("─" * 78)
    print(label)
    print("─" * 78)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit docs/internal/front/ for broken references.",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Also print asset coverage and page size distribution (informational).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print nothing on success (still exits 1 on failure).",
    )
    args = parser.parse_args(argv)

    if not FRONT.exists():
        print(f"front docs directory missing: {FRONT}", file=sys.stderr)
        return 1

    pages = collect_pages()
    failures = 0

    # 1. Broken hrefs/srcs.
    broken_links: list[dict] = []
    for p in pages:
        broken_links.extend(scan_links(p))

    # 2. Sidebar paths.
    sidebar_missing = sidebar_paths_check()

    # 3. Prose mentions.
    phantom_mentions: list[dict] = []
    for p in pages:
        phantom_mentions.extend(scan_prose_mentions(p))

    failures = (
        (1 if broken_links else 0) + (1 if sidebar_missing else 0) + (1 if phantom_mentions else 0)
    )

    if failures or not args.quiet:
        print("=" * 78)
        print("FRONT DOCS AUDIT")
        print("=" * 78)
        print(f"\nPages scanned: {len(pages)}\n")

        hr("1. BROKEN href/src REFERENCES")
        if broken_links:
            current_page = ""
            for it in broken_links:
                if it["page"] != current_page:
                    current_page = it["page"]
                    print(f"\n  {current_page}")
                print(f"    line {it['line']:>4}  href={it['href']!r}")
                print(f"              → {it['resolved']} (missing)")
            print(f"\n  TOTAL BROKEN: {len(broken_links)}")
        else:
            print("\n  ✓ No broken hrefs/srcs.")

        print()
        hr("2. SIDEBAR NAV PATH VALIDITY (internal-sidebar.js)")
        if sidebar_missing:
            print(f"\n  MISSING ({len(sidebar_missing)}):")
            for m in sidebar_missing:
                print(f"    {m}")
        else:
            print("\n  ✓ All sidebar paths resolve.")

        print()
        hr("3. PROSE MENTIONS OF NON-EXISTENT FILES")
        if phantom_mentions:
            current_page = ""
            for it in phantom_mentions:
                if it["page"] != current_page:
                    current_page = it["page"]
                    print(f"\n  {current_page}")
                print(f"    line {it['line']:>4}  mention={it['mention']!r}")
            print(f"\n  TOTAL PHANTOM MENTIONS: {len(phantom_mentions)}")
        else:
            print("\n  ✓ No phantom prose mentions.")

    if args.coverage:
        print()
        hr("4. ASSET COVERAGE — docs/assets/*.{js,css} mentions in front docs")
        cov = asset_coverage()
        print(f"\n  {'asset':<38} {'size':>8} {'mentions':>9} {'pages':>6}")
        print(f"  {'-' * 38} {'-' * 8} {'-' * 9} {'-' * 6}")
        for name, info in sorted(cov.items(), key=lambda kv: kv[1]["total_mentions"]):
            marker = "  ⚠" if info["total_mentions"] == 0 else "   "
            print(
                f"{marker}{name:<38} {info['size']:>8} "
                f"{info['total_mentions']:>9} {len(info['pages']):>6}"
            )
        zero = [n for n, info in cov.items() if info["total_mentions"] == 0]
        if zero:
            print(f"\n  UNDOCUMENTED ASSETS ({len(zero)}): {', '.join(zero)}")

        print()
        hr("5. PAGE SIZE DISTRIBUTION")
        print(f"\n  {'page':<70} {'lines':>6} {'bytes':>7}")
        for path, lines, byts in page_sizes():
            bucket = ""
            if lines > 800:
                bucket = "  [BIG]"
            elif lines < 200:
                bucket = "  [thin]"
            print(f"  {str(path):<70} {lines:>6} {byts:>7}{bucket}")

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
