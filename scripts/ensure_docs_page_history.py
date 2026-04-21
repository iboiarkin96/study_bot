"""Insert a standard ``Page history`` section before ``docs-inpage-toc-mount`` when missing.

Skips ``docs/api/**``, ``docs/assets/**``, and redirect stubs. Skips pages that already have
``<section id="page-history">`` or legacy ``Document history`` / ``5-document-history`` (migrate those separately).

Run: ``python scripts/ensure_docs_page_history.py``
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

TOC_MOUNT_RE = re.compile(
    r'^(\s*)<div class="docs-inpage-toc-mount" data-inpage-toc="auto">\s*</div>\s*$',
    re.MULTILINE,
)

BASELINE_DATE = "2026-04-21"
BASELINE_CHANGE = "Added Page history section (repository baseline)."
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


def _rel_href(from_dir: str, target_rel_path: str) -> str:
    from_parts = _normalize_parts(from_dir.split("/"))
    target_parts = _normalize_parts(target_rel_path.split("/"))
    i = 0
    while i < len(from_parts) and i < len(target_parts) and from_parts[i] == target_parts[i]:
        i += 1
    up = [".."] * (len(from_parts) - i)
    down = target_parts[i:]
    joined = "/".join(up + down)
    return joined or "."


def _profile_href_for(rel_from_docs: str) -> str:
    parts = rel_from_docs.replace("\\", "/").split("/")
    d = "/".join(parts[:-1]) if len(parts) > 1 else ""
    return _rel_href(d, PROFILE_PATH)


def _author_td(rel_from_docs: str) -> str:
    href = _profile_href_for(rel_from_docs)
    return f'<td><a href="{href}">Ivan Boyarkin</a></td>'


def _is_redirect(text: str) -> bool:
    if re.search(r'http-equiv\s*=\s*["\']refresh["\']', text, re.I):
        return True
    low = text.lower()
    if "window.location.replace(" in low and 'rel="canonical"' in low:
        return True
    if "<title>moved" in low:
        return True
    return False


def _has_page_history(text: str) -> bool:
    return 'id="page-history"' in text or "id='page-history'" in text


def _has_legacy_history_heading(text: str) -> bool:
    """Pages that need manual migration from Document history → Page history."""
    if "<h2>Document history</h2>" in text:
        return True
    if "5-document-history" in text:
        return True
    if 'id="history"' in text and "Document history" in text:
        return True
    return bool(re.search(r"<h2[^>]*>\s*5\.\s*Document history\s*</h2>", text))


def _page_history_block(indent: str, rel_from_docs: str) -> str:
    """indent = leading whitespace before <div class="docs-inpage-toc-mount">."""
    i2 = indent + "  "
    i3 = indent + "    "
    i4 = indent + "      "
    i5 = indent + "        "
    return (
        f'{indent}<section id="page-history" class="card">\n'
        f"{i2}<h2>Page history</h2>\n"
        f'{i2}<div class="docs-table-scroll" role="region" aria-label="Page history">\n'
        f'{i3}<table class="docs-page-history">\n'
        f"{i4}<thead>\n"
        f"{i5}<tr>\n"
        f'{i5}  <th scope="col">Date</th>\n'
        f'{i5}  <th scope="col">Change</th>\n'
        f'{i5}  <th scope="col">Author</th>\n'
        f"{i5}</tr>\n"
        f"{i4}</thead>\n"
        f"{i4}<tbody>\n"
        f"{i5}<tr>\n"
        f'{i5}  <td><time datetime="{BASELINE_DATE}">{BASELINE_DATE}</time></td>\n'
        f"{i5}  <td>{BASELINE_CHANGE}</td>\n"
        f"{i5}  {_author_td(rel_from_docs)}\n"
        f"{i5}</tr>\n"
        f"{i4}</tbody>\n"
        f"{i3}</table>\n"
        f"{i2}</div>\n"
        f"{indent}</section>\n"
        f"\n"
    )


def process_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if _is_redirect(text):
        return False
    if "<main" not in text or 'class="container"' not in text:
        return False
    if _has_page_history(text):
        return False
    if _has_legacy_history_heading(text):
        return False
    m = TOC_MOUNT_RE.search(text)
    if not m:
        return False
    indent = m.group(1)
    rel = path.relative_to(DOCS).as_posix()
    block = _page_history_block(indent, rel)
    new_text = TOC_MOUNT_RE.sub(block + m.group(0), text, count=1)
    if new_text == text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    n = 0
    for path in sorted(DOCS.rglob("*.html")):
        rel = path.relative_to(DOCS).as_posix()
        if rel.startswith("api/") or rel.startswith("assets/"):
            continue
        try:
            if process_file(path):
                n += 1
                print(f"+ {rel}")
        except OSError as e:
            print(f"! {rel}: {e}", file=sys.stderr)
    print(f"→ Inserted Page history in {n} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
