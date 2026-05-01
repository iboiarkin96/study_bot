"""Validate design-consistency baseline for docs HTML pages.

This check enforces the shared page skeleton from
``docs/internal/front/documentation-style-guide.html`` for non-generated docs pages.
Generated Python API HTML under ``docs/pdoc/`` is skipped (same as legacy ``docs/api/`` output).
It is intentionally lightweight: fail only on clear structural regressions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import html5lib

ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = ROOT / "docs"
FROZEN_DOCS_REL_PATHS = {
    Path("internal/portal/people/ivan-boyarkin/sa-growth.html"),
    # Standalone week backlog calendar (custom layout, not portal doc skeleton).
    Path("internal/portal/people/ivan-boyarkin/week-calendar-2026-04-25.html"),
}


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _iter_docs_pages(candidates: list[str] | None = None) -> list[Path]:
    pages: list[Path] = []
    if candidates:
        raw_paths = [Path(item).resolve() for item in candidates]
    else:
        raw_paths = sorted(DOCS_ROOT.glob("**/*.html"))

    for path in raw_paths:
        if not path.is_file() or path.suffix.lower() != ".html":
            continue
        if DOCS_ROOT not in path.parents:
            continue
        rel = path.relative_to(DOCS_ROOT)
        if rel.parts and rel.parts[0] in {"api", "assets", "pdoc"}:
            continue
        if rel in FROZEN_DOCS_REL_PATHS:
            continue
        pages.append(path)
    return pages


def _is_redirect_stub(root_el, text: str) -> bool:
    for node in root_el.iter():
        if not isinstance(node.tag, str):
            continue
        if _local_name(node.tag) != "meta":
            continue
        equiv = (node.attrib.get("http-equiv") or "").lower()
        if equiv == "refresh":
            return True
    lowered = text.lower()
    if "window.location.replace(" in lowered and 'rel="canonical"' in lowered:
        return True
    if "<title>moved" in lowered:
        return True
    return False


def _has_docs_css(root_el) -> bool:
    for node in root_el.iter():
        if not isinstance(node.tag, str) or _local_name(node.tag) != "link":
            continue
        if (node.attrib.get("rel") or "").lower() != "stylesheet":
            continue
        href = (node.attrib.get("href") or "").lower()
        if "docs.css" in href:
            return True
    return False


def _has_docs_nav_script(root_el) -> bool:
    for node in root_el.iter():
        if not isinstance(node.tag, str) or _local_name(node.tag) != "script":
            continue
        src = (node.attrib.get("src") or "").lower()
        if "docs-nav.js" in src:
            return True
    return False


def _find_main_container(root_el) -> bool:
    for node in root_el.iter():
        if not isinstance(node.tag, str) or _local_name(node.tag) != "main":
            continue
        classes = set((node.attrib.get("class") or "").split())
        if "container" in classes:
            return True
    return False


def _is_swagger_layout(root_el) -> bool:
    for node in root_el.iter():
        if not isinstance(node.tag, str) or _local_name(node.tag) != "main":
            continue
        classes = set((node.attrib.get("class") or "").split())
        if "container--swagger" in classes:
            return True
    return False


def _has_top_nav_mount(root_el) -> bool:
    for node in root_el.iter():
        if not isinstance(node.tag, str) or _local_name(node.tag) != "div":
            continue
        if node.attrib.get("id") == "docs-top-nav":
            return True
    return False


def _count_tag(root_el, tag_name: str) -> int:
    count = 0
    for node in root_el.iter():
        if isinstance(node.tag, str) and _local_name(node.tag) == tag_name:
            count += 1
    return count


def _has_section_card(root_el) -> bool:
    for node in root_el.iter():
        if not isinstance(node.tag, str) or _local_name(node.tag) != "section":
            continue
        classes = set((node.attrib.get("class") or "").split())
        if "card" in classes:
            return True
    return False


def _has_page_history_section(root_el) -> bool:
    """Standard hub pages use id=page-history; assessment reports use id=5-page-history."""
    for node in root_el.iter():
        if not isinstance(node.tag, str) or _local_name(node.tag) != "section":
            continue
        sid = (node.attrib.get("id") or "").strip()
        if sid in ("page-history", "5-page-history"):
            return True
    return False


def _has_body_maintainers(root_el) -> bool:
    for node in root_el.iter():
        if not isinstance(node.tag, str) or _local_name(node.tag) != "body":
            continue
        maintainer_ids = (node.attrib.get("data-maintainer-ids") or "").strip()
        return bool(maintainer_ids)
    return False


def main() -> None:
    parser = html5lib.HTMLParser(tree=html5lib.getTreeBuilder("etree"))
    failures: list[str] = []

    for path in _iter_docs_pages(sys.argv[1:]):
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        doc = parser.parse(text)
        if parser.errors:
            failures.append(f"{rel}: HTML5 parse errors ({len(parser.errors)})")
            parser.errors.clear()
            continue

        redirect_stub = _is_redirect_stub(doc, text)

        if not _has_docs_css(doc):
            failures.append(f"{rel}: missing docs.css stylesheet link")
        if not _has_docs_nav_script(doc):
            failures.append(f"{rel}: missing docs-nav.js script link")

        if not redirect_stub:
            swagger_layout = _is_swagger_layout(doc)
            if not _find_main_container(doc):
                failures.append(f'{rel}: missing <main class="container"> baseline')
            if _count_tag(doc, "h1") != 1:
                failures.append(f"{rel}: expected exactly one <h1>")
            if not _has_top_nav_mount(doc):
                failures.append(f'{rel}: missing <div id="docs-top-nav"></div>')
            if not swagger_layout and not _has_section_card(doc):
                failures.append(f'{rel}: expected at least one <section class="card">')
            if not swagger_layout and not _has_page_history_section(doc):
                failures.append(
                    f"{rel}: missing Page history section "
                    f'(<section id="page-history"> or assessment <section> with id="5-page-history"); '
                    f"see docs/internal/front/documentation-style-guide.html#page-history"
                )
            if not _has_body_maintainers(doc):
                failures.append(
                    f'{rel}: missing <body data-maintainer-ids="..."> required for the Edited by block'
                )

        if '<div class="card"' in text:
            failures.append(
                f'{rel}: legacy \'<div class="card">\' found; use <section class="card">'
            )

    if failures:
        print("Docs design baseline check failed:")
        for item in failures:
            print(f" - {item}")
        raise SystemExit(1)

    print("Docs design baseline check passed")


if __name__ == "__main__":
    main()
