"""Render selected docs markdown files to HTML companions."""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET_DIRS = ("docs/adr", "docs/developer", "docs/runbooks")

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_CODE_RE = re.compile(r"`([^`]+)`")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_LIST_ITEM_RE = re.compile(r"^(\s*)([-*+]|\d+\.)\s+(.*)$")


def _inline(text: str) -> str:
    """Escape HTML and turn markdown links and backticks into simple HTML.

    Args:
        text: Single line or fragment without block-level markdown.

    Returns:
        Escaped string with ``<a>`` and ``<code>`` where patterns match.
    """
    safe = escape(text)
    safe = _LINK_RE.sub(r'<a href="\2">\1</a>', safe)
    safe = _CODE_RE.sub(r"<code>\1</code>", safe)
    return safe


def _title(markdown: str, fallback: str) -> str:
    """Take the first ATX H1 line as page title, or use ``fallback``.

    Args:
        markdown: Full markdown source.
        fallback: Title when no ``# `` line exists.

    Returns:
        Stripped title string.
    """
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _markdown_to_html(markdown: str) -> str:
    """Convert a subset of markdown (headings, lists, fenced code, hr, paragraphs) to HTML.

    Args:
        markdown: Full document text.

    Returns:
        HTML body fragment (no ``<html>`` wrapper).
    """
    lines = markdown.splitlines()
    out: list[str] = []
    in_code = False
    code_lines: list[str] = []
    list_stack: list[str] = []
    li_open: list[bool] = []

    def close_li(level: int) -> None:
        """Close an open ``<li>`` at ``level`` if one was left open."""
        if 0 <= level < len(li_open) and li_open[level]:
            out.append("</li>")
            li_open[level] = False

    def open_list(kind: str) -> None:
        """Push a new ``ul``/``ol`` onto the list stack and track list item state."""
        out.append(f"<{kind}>")
        list_stack.append(kind)
        li_open.append(False)

    def close_last_list() -> None:
        """Close the innermost open list tag and pop its stack entry."""
        if not list_stack:
            return
        level = len(list_stack) - 1
        close_li(level)
        out.append(f"</{list_stack[level]}>")
        list_stack.pop()
        li_open.pop()

    def close_all_lists() -> None:
        """Close all nested lists (used before hr, headings, code fences)."""
        while list_stack:
            close_last_list()

    def close_code() -> None:
        """Flush accumulated fenced-code lines as a single ``<pre><code>`` block."""
        nonlocal in_code, code_lines
        if in_code:
            while code_lines and not code_lines[0].strip():
                code_lines.pop(0)
            while code_lines and not code_lines[-1].strip():
                code_lines.pop()
            out.append("<pre><code>")
            out.append(escape("\n".join(code_lines)))
            out.append("</code></pre>")
            in_code = False
            code_lines = []

    for raw in lines:
        line = raw.rstrip("\n")
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                close_code()
            else:
                close_all_lists()
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if stripped == "---":
            close_all_lists()
            out.append("<hr />")
            continue

        heading = _HEADING_RE.match(stripped)
        if heading:
            close_all_lists()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2).strip())}</h{level}>")
            continue

        list_match = _LIST_ITEM_RE.match(line)
        if list_match:
            indent = len(list_match.group(1).replace("\t", "    "))
            level = indent // 2
            marker = list_match.group(2)
            item_text = list_match.group(3).strip()
            kind = "ol" if marker.endswith(".") and marker[:-1].isdigit() else "ul"

            while len(list_stack) > level + 1:
                close_last_list()

            while len(list_stack) < level + 1:
                open_list(kind if len(list_stack) == level else "ul")

            if list_stack and list_stack[-1] != kind:
                close_last_list()
                open_list(kind)

            current_level = len(list_stack) - 1
            close_li(current_level)
            out.append(f"<li>{_inline(item_text)}")
            li_open[current_level] = True
            continue

        if not stripped:
            close_all_lists()
            continue

        if list_stack and line.startswith("  "):
            current_level = len(list_stack) - 1
            if not li_open[current_level]:
                out.append("<li>")
                li_open[current_level] = True
            out.append(f"<br />{_inline(stripped)}")
            continue

        close_all_lists()
        out.append(f"<p>{_inline(stripped)}</p>")

    close_all_lists()
    close_code()
    return "\n".join(out)


def _render_page(md_path: Path) -> str:
    """Read markdown from ``md_path`` and wrap converted body in a minimal HTML shell.

    Args:
        md_path: Path to a ``.md`` file under :data:`TARGET_DIRS`.

    Returns:
        Full HTML document string with shared stylesheet link.
    """
    markdown = md_path.read_text(encoding="utf-8")
    page_title = _title(markdown, md_path.stem.replace("-", " ").title())
    body = _markdown_to_html(markdown)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(page_title)}</title>
  <link rel="stylesheet" href="../assets/docs.css" />
</head>
<body>
  <main class="container">
{body}
  </main>
</body>
</html>
"""


def main() -> None:
    """Scan ``docs/adr``, ``docs/developer``, ``docs/runbooks`` for ``*.md`` and write ``*.html``.

    Prints how many HTML files were updated when content changed.
    """
    updated = 0
    for dir_rel in TARGET_DIRS:
        folder = ROOT / dir_rel
        if not folder.exists():
            continue
        for md_path in sorted(folder.glob("*.md")):
            html_path = md_path.with_suffix(".html")
            rendered = _render_page(md_path)
            current = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
            if rendered != current:
                html_path.write_text(rendered, encoding="utf-8")
                updated += 1
    print(f"Rendered HTML companions: {updated} updated")


if __name__ == "__main__":
    main()
