"""Structural lint for internal analyst-spec pages.

Operation specs under ``docs/internal/api/<resource>/operations/*.html`` follow the template at
``docs/internal/api/_shared/spec-template.html``. The template marks every required section with
``data-spec-section="<id>"`` and ``data-spec-required="true"``; this script verifies that each
real operation spec carries the same section IDs, that none is empty (only ``TODO`` content),
and that the body-level metadata is present and consistent with the metadata strip.

Exit codes:
    0 — all checked specs pass.
    1 — at least one spec failed the lint or there is an internal script error.

Usage::

    python scripts/spec_lint.py                          # lint every operation spec
    python scripts/spec_lint.py --paths <file> <file>    # lint a specific list of files
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OPERATIONS_GLOB = "docs/internal/api/*/operations/*.html"

REQUIRED_SECTIONS: tuple[str, ...] = (
    "business-context",
    "user-stories",
    "acceptance-criteria",
    "functional-requirements",
    "non-functional-requirements",
    "authorization",
    "request-contract",
    "response-contract",
    "side-effects",
    "idempotency-concurrency",
    "error-catalog",
    "edge-cases",
    "observability",
    "test-plan",
    "openapi-authoring-hints",
    "open-questions",
    "out-of-scope",
    "traceability",
    "changelog",
    "page-history",
)

OPTIONAL_SECTIONS: tuple[str, ...] = ("state-transitions",)

ALLOWED_STATUSES: tuple[str, ...] = (
    "draft",
    "in-review",
    "approved",
    "implemented",
    "deprecated",
)

# Permitted text inside an "open-questions" or "out-of-scope" section when nothing applies.
EMPTY_PLACEHOLDER_OK = re.compile(r"\bNone\.\b")


class LintError(Exception):
    """Raised when a spec fails the structural lint."""


def find_operation_specs(repo_root: Path) -> list[Path]:
    """Return every operation-spec HTML file under the repository.

    Args:
        repo_root: Repository root used to anchor the glob.

    Returns:
        Sorted list of absolute paths matching :data:`OPERATIONS_GLOB`.
    """
    return sorted(repo_root.glob(OPERATIONS_GLOB))


def _attribute(html: str, attr: str, *, on_tag: str = "body") -> str | None:
    """Extract the value of ``attr`` from the first opening ``<{on_tag} ...>`` tag.

    Args:
        html: Whole-document HTML source.
        attr: Attribute name to look up (e.g. ``data-spec-status``).
        on_tag: Tag name that hosts the attribute. ``body`` by default.

    Returns:
        Attribute value, or ``None`` if the tag or attribute is missing.
    """
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
    """Locate a ``<section data-spec-section="<section_id>" ...>...</section>`` block.

    Args:
        html: Whole-document HTML source.
        section_id: Value of ``data-spec-section`` to find.

    Returns:
        Tuple ``(open_tag, body)`` of the matching section, or ``None`` if absent. ``body``
        is the inner HTML between the opening and closing tags. Naive parser — assumes the
        operation specs do not nest one ``data-spec-section`` inside another, which the
        template guarantees.
    """
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
    """Remove HTML tags and collapse whitespace, returning visible text only.

    Args:
        s: HTML fragment.

    Returns:
        Text content with all tags stripped and runs of whitespace collapsed to single spaces.
    """
    no_tags = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", no_tags).strip()


def _is_section_filled(section_id: str, body: str) -> tuple[bool, str]:
    """Heuristic check that a section has real content rather than a lone TODO placeholder.

    Args:
        section_id: ``data-spec-section`` value.
        body: Inner HTML of the section.

    Returns:
        ``(ok, reason)``. ``ok`` is True when the section appears to be filled. ``reason`` is
        a short human-readable explanation when not OK.
    """
    text = _strip_tags(body)
    if not text:
        return False, "section body is empty"
    todo_only = re.sub(r"TODO\([^)]+\):.*?(?:\.|$)", "", text, flags=re.IGNORECASE).strip()
    if not todo_only:
        return False, "section contains only TODO(...) placeholder text"
    if section_id in {"open-questions", "out-of-scope"} and not EMPTY_PLACEHOLDER_OK.search(text):
        # Allow either listed items or the literal "None." token; both already covered by
        # todo_only being non-empty when items are listed. The dedicated "None." check is here
        # to avoid the "TODO" auto-pass below for stub specs that just left the placeholder.
        if "TODO" in text and len(todo_only) < 5:
            return False, 'section is empty without explicit "None."'
    return True, ""


def _has_example_block(html: str) -> bool:
    """True iff the document contains at least one ``<pre><code>...</code></pre>`` block."""
    return bool(re.search(r"<pre[^>]*>\s*<code\b", html, flags=re.IGNORECASE | re.DOTALL))


def _has_status_mount(html: str) -> bool:
    """True iff the page has at least one ``[data-spec-status-mount]`` element.

    The element is hydrated into a premium status pill by ``docs-spec-status.js``;
    its presence is the structural marker that replaces the legacy inline badge.
    """
    return bool(re.search(r"\bdata-spec-status-mount\b", html, flags=re.IGNORECASE))


def _loads_status_script(html: str) -> bool:
    """True iff the page links ``docs-spec-status.js`` so the mount actually hydrates."""
    return bool(re.search(r"docs-spec-status\.js", html))


def _has_page_history_row(html: str) -> bool:
    """Check that the page-history section has at least one ``<tbody><tr>`` data row."""
    section = _find_section(html, "page-history")
    if section is None:
        return False
    body = section[1]
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", body, flags=re.DOTALL | re.IGNORECASE)
    if tbody_match is None:
        return False
    return bool(re.search(r"<tr\b", tbody_match.group(1), flags=re.IGNORECASE))


def lint_spec(path: Path) -> list[str]:
    """Lint one operation spec page and return a list of human-readable error messages.

    Args:
        path: Absolute path to the operation spec HTML file.

    Returns:
        Empty list when the spec passes; otherwise one entry per violation.
    """
    html = path.read_text(encoding="utf-8")
    errors: list[str] = []

    # Body-level metadata.
    spec_page = _attribute(html, "data-spec-page")
    if spec_page != "operation":
        errors.append(f'<body data-spec-page="..."> must be "operation" (got {spec_page!r})')

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

    op_id = _attribute(html, "data-spec-operation-id")
    if not op_id:
        errors.append('<body data-spec-operation-id="..."> is missing')

    # Required sections.
    for section_id in REQUIRED_SECTIONS:
        located = _find_section(html, section_id)
        if located is None:
            errors.append(f'required section "{section_id}" is missing')
            continue
        open_tag, body = located
        if 'data-spec-required="true"' not in open_tag:
            errors.append(
                f'section "{section_id}" must declare data-spec-required="true"',
            )
        ok, reason = _is_section_filled(section_id, body)
        if not ok:
            errors.append(f'section "{section_id}": {reason}')

    # Page history must have at least one entry.
    if not _has_page_history_row(html):
        errors.append("page-history table has no <tbody><tr> entries")

    # At least one request/response example.
    if not _has_example_block(html):
        errors.append("no <pre><code>...</code></pre> example found")

    # Sanity: required sections that exist also must not be marked optional by mistake.
    for section_id in OPTIONAL_SECTIONS:
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

    return errors


def _format_report(results: dict[Path, list[str]], repo_root: Path) -> str:
    """Render a human-readable report from lint results.

    Args:
        results: Mapping of spec path to a list of lint errors (empty when passed).
        repo_root: Repository root used to render relative paths.

    Returns:
        Multi-line report string (always at least one line).
    """
    lines: list[str] = []
    failed = 0
    for path, errors in sorted(results.items()):
        rel = path.relative_to(repo_root)
        if not errors:
            lines.append(f"OK   {rel}")
            continue
        failed += 1
        lines.append(f"FAIL {rel}")
        for err in errors:
            lines.append(f"     - {err}")
    summary = f"\nspec_lint: {len(results)} specs, {failed} failed, {len(results) - failed} passed"
    lines.append(summary)
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument vector. ``None`` defers to :data:`sys.argv`.

    Returns:
        Process exit code (0 on success, 1 on lint failure or internal error).
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths",
        nargs="*",
        type=Path,
        help="Optional explicit list of spec paths; defaults to every operation page.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.paths:
        targets = [p if p.is_absolute() else (REPO_ROOT / p) for p in args.paths]
    else:
        targets = find_operation_specs(REPO_ROOT)

    if not targets:
        print("spec_lint: no operation specs found", file=sys.stderr)
        return 1

    results = {path: lint_spec(path) for path in targets}
    report = _format_report(results, REPO_ROOT)
    failed = any(errors for errors in results.values())
    print(report, file=sys.stderr if failed else sys.stdout)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
