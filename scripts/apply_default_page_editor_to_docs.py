"""Add default Page editors (data-maintainer-ids + mount + scripts) to hand-written docs HTML.

Skips ``docs/api/**`` (pdoc regenerates) and ``docs/assets/**`` (fragments).
Skips ``docs/internal/portal/people/*/index.html`` (person profiles).

Run from repo root: ``python scripts/apply_default_page_editor_to_docs.py``
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS = PROJECT_ROOT / "docs"

DEFAULT_MAINTAINER_ID = "16fc8b78537109162984a2fdbef6e142"

DOCS_TOP_NAV_RE = re.compile(
    r'(<div\s+id="docs-top-nav"[^>]*>\s*</div>)',
    re.IGNORECASE | re.DOTALL,
)


def _asset_prefix(rel_from_docs_root: str) -> str:
    parts = rel_from_docs_root.replace("\\", "/").split("/")
    depth = max(0, len(parts) - 1)
    if depth == 0:
        return "./assets/"
    return "../" * depth + "assets/"


def _merge_body_attributes(attrs: str) -> str:
    if re.search(r"data-maintainer-ids\s*=", attrs, re.I):

        def repl(m: re.Match[str]) -> str:
            q = m.group(1)
            raw = m.group(2).strip()
            ids = [x.strip() for x in raw.split(",") if x.strip()]
            if DEFAULT_MAINTAINER_ID not in ids:
                ids.insert(0, DEFAULT_MAINTAINER_ID)
            return f"data-maintainer-ids={q}{','.join(ids)}{q}"

        return re.sub(
            r"data-maintainer-ids\s*=\s*(['\"])([^'\"]*)['\"]",
            repl,
            attrs,
            count=1,
            flags=re.I,
        )
    return attrs.rstrip() + f' data-maintainer-ids="{DEFAULT_MAINTAINER_ID}"'


def _has_script(html: str, name: str) -> bool:
    return bool(re.search(rf'src=["\'][^"\']*{re.escape(name)}[^"\']*["\']', html))


def _inject_scripts(head_inner: str, prefix: str) -> str:
    if _has_script(head_inner, "docs-portal-data.js") and _has_script(
        head_inner, "docs-internal-meta.js"
    ):
        return head_inner
    block = (
        f'  <script defer src="{prefix}docs-portal-data.js"></script>\n'
        f'  <script defer src="{prefix}docs-internal-meta.js"></script>\n'
    )
    m = re.search(
        r'<script\s+defer\s+src=["\'][^"\']*docs-nav\.js["\']\s*>\s*</script>',
        head_inner,
        re.I,
    )
    if m:
        insert_at = m.end()
        return head_inner[:insert_at] + "\n" + block + head_inner[insert_at:]
    return block + head_inner


def process_file(path: Path, rel: str) -> bool:
    text = path.read_text(encoding="utf-8")
    orig = text

    if 'id="docs-top-nav"' not in text and "id='docs-top-nav'" not in text:
        return False

    if 'id="docs-page-meta-mount"' not in text and "id='docs-page-meta-mount'" not in text:
        m = DOCS_TOP_NAV_RE.search(text)
        if m:
            text = (
                text[: m.end()]
                + '\n        <div id="docs-page-meta-mount" hidden></div>'
                + text[m.end() :]
            )

    body_m = re.search(r"<body([^>]*)>", text, re.I | re.DOTALL)
    if body_m:
        attrs = body_m.group(1)
        new_attrs = _merge_body_attributes(attrs)
        if new_attrs != attrs:
            text = text[: body_m.start()] + "<body" + new_attrs + ">" + text[body_m.end() :]

    prefix = _asset_prefix(rel)
    head_open = re.search(r"<head\b[^>]*>", text, re.I | re.DOTALL)
    head_close = re.search(r"</head>", text, re.I)
    if head_open and head_close:
        inner = text[head_open.end() : head_close.start()]
        new_inner = _inject_scripts(inner, prefix)
        if new_inner != inner:
            text = text[: head_open.end()] + new_inner + text[head_close.start() :]

    if text != orig:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> int:
    n_changed = 0
    for path in sorted(DOCS.rglob("*.html")):
        rel = path.relative_to(DOCS).as_posix()
        if rel.startswith("assets/") or rel.startswith("api/"):
            continue
        if re.match(r"internal/portal/people/[^/]+/index\.html$", rel):
            continue
        try:
            if process_file(path, rel):
                n_changed += 1
                print(f"updated {rel}")
        except OSError as e:
            print(f"skip {rel}: {e}", file=sys.stderr)
    print(f"→ Done. Updated {n_changed} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
