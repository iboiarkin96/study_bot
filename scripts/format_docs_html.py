"""Normalize documentation HTML files to a shared visual template."""

from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = ROOT / "docs"

NAV_ITEMS: tuple[tuple[str, Path], ...] = (
    ("System Analysis", DOCS_ROOT / "system-analysis.html"),
    ("Engineering Practices", DOCS_ROOT / "engineering-practices.html"),
    ("Developer Docs", DOCS_ROOT / "developer" / "README.html"),
    ("ADR", DOCS_ROOT / "adr" / "README.html"),
    ("Runbooks", DOCS_ROOT / "runbooks" / "README.html"),
)

STYLE_BLOCK_RE = re.compile(r"(?is)\s*<style>.*?</style>\s*")
STYLESHEET_TAG_RE = re.compile(r'(?ims)^[ \t]*<link\s+rel="stylesheet"[^>]*>\s*')
TOP_NAV_RE = re.compile(r'(?ims)^[ \t]*<nav class="top-nav"[^>]*>.*?</nav>\s*')
MAIN_WITHOUT_CLASS_RE = re.compile(r"(?is)<main(?![^>]*class=)([^>]*)>")
H1_RE = re.compile(r"(?is)<h1[^>]*>.*?</h1>")
TAG_NAME_RE = re.compile(r"^</?\s*([a-zA-Z0-9:_-]+)")
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


def _rel_href(current_file: Path, target_file: Path) -> str:
    rel = os.path.relpath(target_file, start=current_file.parent).replace("\\", "/")
    return rel if rel.startswith(".") else f"./{rel}"


def _active_nav_target(current_file: Path) -> Path:
    rel = current_file.relative_to(DOCS_ROOT)
    if rel.parts[0] == "adr":
        return DOCS_ROOT / "adr" / "README.html"
    if rel.parts[0] == "developer":
        return DOCS_ROOT / "developer" / "README.html"
    if rel.parts[0] == "runbooks":
        return DOCS_ROOT / "runbooks" / "README.html"
    if rel.name == "engineering-practices.html":
        return DOCS_ROOT / "engineering-practices.html"
    return DOCS_ROOT / "system-analysis.html"


def _nav_block(current_file: Path) -> str:
    active_target = _active_nav_target(current_file)
    link_lines: list[str] = []
    for label, target in NAV_ITEMS:
        class_attr = ' class="is-active" aria-current="page"' if target == active_target else ""
        link_lines.append(
            f'      <a href="{_rel_href(current_file, target)}"{class_attr}>{label}</a>'
        )
    links = "\n".join(link_lines)
    return f'    <nav class="top-nav" aria-label="Documentation navigation">\n{links}\n    </nav>'


def _normalize_stylesheet(text: str, current_file: Path) -> str:
    normalized = STYLE_BLOCK_RE.sub("\n", text)
    href = _rel_href(current_file, DOCS_ROOT / "assets" / "docs.css")
    link_line = f'  <link rel="stylesheet" href="{href}" />'
    if STYLESHEET_TAG_RE.search(normalized):
        normalized = STYLESHEET_TAG_RE.sub(f"{link_line}\n", normalized, count=1)
    elif "</head>" in normalized:
        normalized = normalized.replace("</head>", f"{link_line}\n</head>", 1)
    return normalized


def _normalize_main(text: str) -> str:
    return MAIN_WITHOUT_CLASS_RE.sub(r'<main class="container"\1>', text)


def _normalize_nav(text: str, current_file: Path) -> str:
    nav = _nav_block(current_file)
    if TOP_NAV_RE.search(text):
        return TOP_NAV_RE.sub(f"{nav}\n", text, count=1)

    h1 = H1_RE.search(text)
    if h1:
        return text[: h1.end()] + "\n" + nav + "\n" + text[h1.end() :]

    return text


def _normalize_newlines(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.rstrip() + "\n"


def _line_tag_name(stripped_line: str) -> str | None:
    match = TAG_NAME_RE.match(stripped_line)
    if not match:
        return None
    return match.group(1).lower()


def _is_inline_closed_tag(stripped_line: str) -> bool:
    tag_name = _line_tag_name(stripped_line)
    if not tag_name:
        return False
    return (
        stripped_line.startswith(f"<{tag_name}")
        and f"</{tag_name}>" in stripped_line
        and not stripped_line.startswith("</")
    )


def _normalize_indentation(text: str) -> str:
    lines = text.split("\n")
    indent = 0
    normalized_lines: list[str] = []

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            normalized_lines.append("")
            continue

        is_closing = stripped.startswith("</")
        if is_closing:
            indent = max(indent - 1, 0)

        normalized_lines.append(("  " * indent) + stripped)

        if stripped.startswith("<!"):
            continue

        tag_name = _line_tag_name(stripped)
        if not tag_name:
            continue

        is_opening = stripped.startswith("<") and not stripped.startswith("</")
        if not is_opening:
            continue
        if stripped.endswith("/>"):
            continue
        if tag_name in VOID_TAGS:
            continue
        if _is_inline_closed_tag(stripped):
            continue

        indent += 1

    return "\n".join(normalized_lines)


def format_html_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = _normalize_stylesheet(original, path)
    updated = _normalize_main(updated)
    updated = _normalize_nav(updated, path)
    updated = _normalize_indentation(updated)
    updated = _normalize_newlines(updated)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    updated_count = 0
    for html_path in sorted(DOCS_ROOT.glob("**/*.html")):
        if format_html_file(html_path):
            updated_count += 1
    print(f"Formatted docs HTML files: {updated_count} updated")


if __name__ == "__main__":
    main()
