"""Structural lint for frontend documentation specs.

Pages under ``docs/internal/front/`` that declare a typed ``data-spec-page`` attribute
(``component`` / ``foundation`` / ``contract``) follow the matching template under
``docs/internal/front/_shared/``. The template marks every required section with
``data-spec-section="<id>"`` and ``data-spec-required="true"``; this script verifies that
each typed page carries the same section IDs, that none is empty (only ``TODO`` content),
and that the body-level metadata is present.

Pages with other ``data-spec-page`` values (``hub``, ``architecture``, ``reference``,
``screen``, ``template``) are skipped — they have looser conventions, governed by the
style guide and the screen template's own checklist.

Exit codes:
    0 — all checked specs pass.
    1 — at least one spec failed the lint or there is an internal script error.

Usage::

    python scripts/front_spec_lint.py                          # lint every typed front spec
    python scripts/front_spec_lint.py --paths <file> <file>    # lint a specific list of files
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONT_GLOB = "docs/internal/front/**/*.html"

# Required and optional sections per page type. Match the templates in
# docs/internal/front/_shared/{component,foundation,contract}-spec-template.html.
SECTION_RULES: dict[str, dict[str, tuple[str, ...]]] = {
    "component": {
        "required": (
            "overview",
            "anatomy",
            "states",
            "accessibility",
            "behavior",
            "do-dont",
            "code-handoff",
            "page-history",
        ),
        "optional": ("related",),
    },
    "foundation": {
        "required": (
            "overview",
            "tokens-values",
            "usage-rules",
            "examples",
            "code-handoff",
            "page-history",
        ),
        "optional": ("related",),
    },
    "contract": {
        "required": (
            "overview",
            "scope",
            "requirements",
            "acceptance",
            "implementation",
            "page-history",
        ),
        "optional": ("visual-reference", "related"),
    },
}

LINTED_TYPES: frozenset[str] = frozenset(SECTION_RULES.keys())

# Page-types that exist in the front directory but are intentionally not linted by this
# script. Listed here so we can warn about *unknown* values instead of silently skipping.
# ``pattern`` is skipped until a pattern spec template lands and defines required sections.
SKIPPED_TYPES: frozenset[str] = frozenset(
    {"hub", "architecture", "reference", "screen", "template", "pattern"}
)

ALLOWED_STATUSES: tuple[str, ...] = (
    "draft",
    "in-progress",
    "implemented",
    "deprecated",
    "template",
)


class LintError(Exception):
    """Raised when a spec fails the structural lint."""


def find_front_specs(repo_root: Path) -> list[Path]:
    """Return every HTML file under ``docs/internal/front/`` recursively."""
    return sorted(repo_root.glob(FRONT_GLOB))


def _attribute(html: str, attr: str, *, on_tag: str = "body") -> str | None:
    """Extract the value of ``attr`` from the first opening ``<{on_tag} ...>`` tag."""
    tag_match = re.search(rf"<{on_tag}\b[^>]*>", html, flags=re.IGNORECASE | re.DOTALL)
    if tag_match is None:
        return None
    attr_match = re.search(
        rf'\b{re.escape(attr)}\s*=\s*"([^"]*)"',
        tag_match.group(0),
        flags=re.IGNORECASE,
    )
    return attr_match.group(1) if attr_match else None


def _find_section(html: str, section_id: str) -> tuple[str, str] | None:
    """Locate ``<section data-spec-section="<section_id>" ...>...</section>``."""
    open_pattern = re.compile(
        rf'<section\b[^>]*\bdata-spec-section\s*=\s*"{re.escape(section_id)}"[^>]*>',
        flags=re.IGNORECASE,
    )
    open_match = open_pattern.search(html)
    if open_match is None:
        return None
    start = open_match.end()
    close = html.find("</section>", start)
    if close == -1:
        return None
    return open_match.group(0), html[start:close]


def _strip_tags(s: str) -> str:
    """Remove HTML tags and collapse whitespace, returning visible text only."""
    no_tags = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", no_tags).strip()


def _is_section_filled(body: str) -> tuple[bool, str]:
    """Heuristic check that a section has real content, not just a TODO placeholder."""
    text = _strip_tags(body)
    if not text:
        return False, "section body is empty"
    todo_only = re.sub(r"TODO\([^)]+\):.*?(?:\.|$)", "", text, flags=re.IGNORECASE).strip()
    if not todo_only:
        return False, "section contains only TODO(...) placeholder text"
    return True, ""


def _has_status_mount(html: str) -> bool:
    """True iff the page has at least one ``[data-spec-status-mount]`` element."""
    return bool(re.search(r"\bdata-spec-status-mount\b", html, flags=re.IGNORECASE))


def _loads_status_script(html: str) -> bool:
    """True iff the page links ``docs-spec-status.js``."""
    return bool(re.search(r"docs-spec-status\.js", html))


def _has_page_history_row(html: str) -> bool:
    """Page-history section has at least one ``<tbody><tr>`` data row."""
    section = _find_section(html, "page-history")
    if section is None:
        return False
    body = section[1]
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", body, flags=re.DOTALL | re.IGNORECASE)
    if tbody_match is None:
        return False
    return bool(re.search(r"<tr\b", tbody_match.group(1), flags=re.IGNORECASE))


def lint_spec(path: Path) -> tuple[str, list[str]]:
    """Lint one front spec page.

    Returns:
        ``(verdict, errors)`` where ``verdict`` is one of ``"OK"``, ``"FAIL"``, ``"SKIP"``.
        ``errors`` is empty unless ``verdict == "FAIL"``.
    """
    html = path.read_text(encoding="utf-8")

    spec_page = _attribute(html, "data-spec-page")
    if spec_page is None:
        # Pages without typing are not in scope (legacy pages, READMEs).
        return "SKIP", []

    if spec_page in SKIPPED_TYPES:
        return "SKIP", []

    if spec_page not in LINTED_TYPES:
        return "FAIL", [
            f"unknown data-spec-page={spec_page!r}; "
            f"expected one of {sorted(LINTED_TYPES | SKIPPED_TYPES)}"
        ]

    # Lint-exempt: the templates themselves carry status="template".
    if _attribute(html, "data-spec-status") == "template":
        return "SKIP", []

    # Forward-looking: only lint pages that have explicitly opted in to the new templates by
    # carrying at least one data-spec-section marker. Pre-template legacy pages are skipped
    # until they are rewritten against a template.
    if not re.search(r"\bdata-spec-section\s*=", html, flags=re.IGNORECASE):
        return "SKIP", []

    errors: list[str] = []

    # Body-level metadata.
    status = _attribute(html, "data-spec-status")
    if not status:
        errors.append('<body data-spec-status="..."> is missing')
    elif status not in ALLOWED_STATUSES:
        errors.append(
            f"data-spec-status={status!r} not in {sorted(ALLOWED_STATUSES)}",
        )
    elif not _has_status_mount(html):
        errors.append(
            "metadata strip lacks a [data-spec-status-mount] element to render the status pill",
        )
    elif not _loads_status_script(html):
        errors.append(
            "page does not link docs-spec-status.js — the status pill will not hydrate",
        )

    if not _attribute(html, "data-spec-owner"):
        errors.append('<body data-spec-owner="..."> is missing')

    # Section rules per page type.
    rules = SECTION_RULES[spec_page]
    for section_id in rules["required"]:
        located = _find_section(html, section_id)
        if located is None:
            errors.append(f'required section "{section_id}" is missing')
            continue
        open_tag, body = located
        if 'data-spec-required="true"' not in open_tag:
            errors.append(
                f'section "{section_id}" must declare data-spec-required="true"',
            )
        ok, reason = _is_section_filled(body)
        if not ok:
            errors.append(f'section "{section_id}": {reason}')

    # Optional sections, when present, must declare data-spec-required="false".
    for section_id in rules["optional"]:
        located = _find_section(html, section_id)
        if located is None:
            continue
        open_tag, _ = located
        marker = re.search(
            r'data-spec-required\s*=\s*"(true|false)"',
            open_tag,
            flags=re.IGNORECASE,
        )
        if marker is None:
            errors.append(
                f'optional section "{section_id}" must declare data-spec-required="false"',
            )

    # Page history must have at least one data row.
    if not _has_page_history_row(html):
        errors.append("page-history table has no <tbody><tr> entries")

    return ("FAIL" if errors else "OK"), errors


def _format_report(
    results: dict[Path, tuple[str, list[str]]],
    repo_root: Path,
) -> str:
    """Render a human-readable report from lint results."""
    lines: list[str] = []
    failed = ok = skipped = 0
    for path, (verdict, errors) in sorted(results.items()):
        rel = path.relative_to(repo_root)
        if verdict == "OK":
            lines.append(f"OK   {rel}")
            ok += 1
        elif verdict == "SKIP":
            skipped += 1
        else:
            lines.append(f"FAIL {rel}")
            for err in errors:
                lines.append(f"     - {err}")
            failed += 1
    summary = (
        f"\nfront_spec_lint: {ok + failed} typed specs checked "
        f"({ok} passed, {failed} failed); {skipped} skipped (untyped or non-linted)."
    )
    lines.append(summary)
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths",
        nargs="+",
        type=Path,
        help="Optional list of HTML files to lint; defaults to every front spec.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    paths: list[Path]
    if args.paths:
        paths = [p.resolve() for p in args.paths]
    else:
        paths = find_front_specs(REPO_ROOT)

    results: dict[Path, tuple[str, list[str]]] = {}
    for path in paths:
        try:
            verdict, errors = lint_spec(path)
        except Exception as exc:
            verdict, errors = "FAIL", [f"internal lint error: {exc}"]
        results[path] = (verdict, errors)

    report = _format_report(results, REPO_ROOT)
    print(report)

    any_failed = any(v == "FAIL" for v, _ in results.values())
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
