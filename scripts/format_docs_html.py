"""Normalize documentation HTML files to a shared visual template."""

from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = ROOT / "docs"

STYLE_BLOCK_RE = re.compile(r"(?is)\s*<style>.*?</style>\s*")
STYLESHEET_TAG_RE = re.compile(r'(?ims)^[ \t]*<link\s+rel="stylesheet"[^>]*>\s*')
TOP_NAV_RE = re.compile(r'(?ims)^[ \t]*<nav class="top-nav"[^>]*>.*?</nav>\s*')
TOP_NAV_HOST_RE = re.compile(r'(?ims)^[ \t]*<div id="docs-top-nav"></div>\s*')
NAV_SCRIPT_TAG_RE = re.compile(
    r'(?ims)^[ \t]*<script\s+defer\s+src="[^"]*docs-nav\.js"[^>]*></script>\s*'
)
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
    """Relative URL from ``current_file``'s directory to ``target_file``.

    Args:
        current_file: HTML file being edited.
        target_file: Asset or link target under the repo.

    Returns:
        POSIX-style relative path, prefixed with ``./`` when it does not start with ``.``.
    """
    rel = os.path.relpath(target_file, start=current_file.parent).replace("\\", "/")
    return rel if rel.startswith(".") else f"./{rel}"


def _normalize_stylesheet(text: str, current_file: Path) -> str:
    """Remove inline ``<style>`` blocks and enforce a single ``docs.css`` link in ``<head>``.

    Args:
        text: Full HTML document text.
        current_file: Path to the file (for relative href to :data:`DOCS_ROOT`).

    Returns:
        Updated HTML string.
    """
    normalized = STYLE_BLOCK_RE.sub("\n", text)
    href = _rel_href(current_file, DOCS_ROOT / "assets" / "docs.css")
    link_line = f'  <link rel="stylesheet" href="{href}" />'
    if STYLESHEET_TAG_RE.search(normalized):
        normalized = STYLESHEET_TAG_RE.sub(f"{link_line}\n", normalized, count=1)
    elif "</head>" in normalized:
        normalized = normalized.replace("</head>", f"{link_line}\n</head>", 1)
    return normalized


def _normalize_main(text: str) -> str:
    """Ensure ``<main>`` has ``class="container"`` when missing.

    Args:
        text: HTML source.

    Returns:
        Text with main tag normalized.
    """
    return MAIN_WITHOUT_CLASS_RE.sub(r'<main class="container"\1>', text)


def _normalize_nav_script(text: str, current_file: Path) -> str:
    """Ensure ``docs-nav.js`` is loaded once from the correct relative path.

    Args:
        text: HTML source.
        current_file: File path for relative script URL resolution.

    Returns:
        Updated HTML.
    """
    script_src = _rel_href(current_file, DOCS_ROOT / "assets" / "docs-nav.js")
    script_line = f'  <script defer src="{script_src}"></script>'
    if NAV_SCRIPT_TAG_RE.search(text):
        return NAV_SCRIPT_TAG_RE.sub(f"{script_line}\n", text, count=1)
    if "</head>" in text:
        return text.replace("</head>", f"{script_line}\n</head>", 1)
    return text


def _normalize_nav(text: str) -> str:
    """Replace legacy top nav markup with the ``docs-top-nav`` host div.

    Args:
        text: HTML after stylesheet/script normalization.

    Returns:
        HTML suitable for client-side nav injection.
    """
    nav_host = '    <div id="docs-top-nav"></div>'
    without_nav = TOP_NAV_RE.sub("", text, count=1)

    if TOP_NAV_HOST_RE.search(without_nav):
        return TOP_NAV_HOST_RE.sub(f"{nav_host}\n", without_nav, count=1)

    h1 = H1_RE.search(without_nav)
    if h1:
        return without_nav[: h1.end()] + "\n" + nav_host + "\n" + without_nav[h1.end() :]

    return without_nav


def _normalize_newlines(text: str) -> str:
    """Normalize line endings and collapse excessive blank lines; ensure trailing newline.

    Args:
        text: Raw HTML.

    Returns:
        Normalized text.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.rstrip() + "\n"


def _line_tag_name(stripped_line: str) -> str | None:
    """Return lowercased HTML tag name for an opening or closing line, if any.

    Args:
        stripped_line: Single line without surrounding whitespace.

    Returns:
        Tag name, or ``None`` if the line does not start like a tag.
    """
    match = TAG_NAME_RE.match(stripped_line)
    if not match:
        return None
    return match.group(1).lower()


def _is_inline_closed_tag(stripped_line: str) -> bool:
    """Return True if ``stripped_line`` contains both open and close of the same tag.

    Args:
        stripped_line: One line of HTML.

    Returns:
        Whether the line is a self-contained inline element (e.g. ``<p>...</p>``).
    """
    tag_name = _line_tag_name(stripped_line)
    if not tag_name:
        return False
    return (
        stripped_line.startswith(f"<{tag_name}")
        and f"</{tag_name}>" in stripped_line
        and not stripped_line.startswith("</")
    )


def _normalize_indentation(text: str) -> str:
    """Re-indent HTML with two spaces per nesting level (skip void and inline-closed tags).

    Args:
        text: HTML with arbitrary indentation.

    Returns:
        Pretty-printed HTML lines.
    """
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
    """Apply all normalizations to one HTML file; write only if content changed.

    Args:
        path: HTML file under :data:`DOCS_ROOT`.

    Returns:
        ``True`` if the file was modified, else ``False``.
    """
    original = path.read_text(encoding="utf-8")
    updated = _normalize_stylesheet(original, path)
    updated = _normalize_nav_script(updated, path)
    updated = _normalize_main(updated)
    updated = _normalize_nav(updated)
    updated = _normalize_indentation(updated)
    updated = _normalize_newlines(updated)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    """Walk all ``docs/**/*.html`` (except ``docs/backlog/**`` and ``docs/api/**``) and normalize in place.

    Prints the count of updated files.
    """
    updated_count = 0
    for html_path in sorted(DOCS_ROOT.glob("**/*.html")):
        try:
            rel = html_path.relative_to(DOCS_ROOT)
        except ValueError:
            continue
        # pdoc output for `make api-docs`; keep generator-owned HTML untouched.
        if rel.parts and rel.parts[0] == "api":
            continue
        if format_html_file(html_path):
            updated_count += 1
    print(f"Formatted docs HTML files: {updated_count} updated")


if __name__ == "__main__":
    main()
