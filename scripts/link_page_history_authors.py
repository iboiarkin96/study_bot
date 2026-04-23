"""Wrap ``Ivan Boyarkin`` in Page history ``<td>`` cells with a link to the portal profile.

Uses the same relative resolution as ``docs-nav.js`` / ``docs-internal-meta.js``.
Run: ``python scripts/link_page_history_authors.py``
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

PROFILE_PATH = "internal/portal/people/ivan-boyarkin/index.html"


def _normalize_parts(parts: list[str]) -> list[str]:
    out: list[str] = []
    for part in parts:
        if not part or part == ".":
            continue
        if part == "..":
            if out:
                out.pop()
            continue
        out.append(part)
    return out


def rel_href(from_dir: str, target_rel_path: str) -> str:
    """Match docs-nav.js ``relHref``."""
    from_parts = _normalize_parts(from_dir.split("/"))
    target_parts = _normalize_parts(target_rel_path.split("/"))
    i = 0
    while i < len(from_parts) and i < len(target_parts) and from_parts[i] == target_parts[i]:
        i += 1
    up = [".."] * (len(from_parts) - i)
    down = target_parts[i:]
    joined = "/".join(up + down)
    return joined or "."


def _dir_from_docs_rel(rel: str) -> str:
    parts = rel.replace("\\", "/").split("/")
    if len(parts) <= 1:
        return ""
    return "/".join(parts[:-1])


def profile_href_for_file(rel: str) -> str:
    d = _dir_from_docs_rel(rel)
    return rel_href(d, PROFILE_PATH)


PLAIN_TD = re.compile(r"<td>Ivan Boyarkin</td>")


def process_file(path: Path) -> bool:
    rel = path.relative_to(DOCS).as_posix()
    text = path.read_text(encoding="utf-8")
    if "Ivan Boyarkin" not in text:
        return False
    if "docs-page-history" not in text and "Page history" not in text:
        return False
    href = profile_href_for_file(rel)
    replacement = f'<td><a href="{href}">Ivan Boyarkin</a></td>'
    new_text, n = PLAIN_TD.subn(replacement, text)
    if n == 0 or new_text == text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    n = 0
    for path in sorted(DOCS.rglob("*.html")):
        rel = path.relative_to(DOCS).as_posix()
        if rel.startswith("api/") or rel.startswith("assets/") or rel.startswith("pdoc/"):
            continue
        try:
            if process_file(path):
                n += 1
                print(f"linked {rel}")
        except OSError as e:
            print(f"! {rel}: {e}", file=sys.stderr)
    print(f"→ Updated {n} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
