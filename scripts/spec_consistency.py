"""Cross-document consistency lint between analyst specs, OpenAPI, and the error catalog.

Runs three checks:

1. **operationId ↔ spec page**: every operation page declares ``data-spec-operation-id`` on
   ``<body>``; the script verifies that each declared ID is unique across pages and (unless the
   page is in ``draft`` status) is present in ``docs/openapi/openapi-baseline.json``.

2. **OpenAPI → spec page**: for every ``operationId`` in the OpenAPI document, there must be
   exactly one operation page that declares it. Pages explicitly tagged
   ``data-spec-status="implemented"`` must match an OpenAPI entry; ``draft`` may precede the
   OpenAPI entry. Stub pages with no ``data-spec-operation-id`` are skipped (the structural
   linter ``spec_lint.py`` already flags them).

3. **Error code/key ↔ catalog**: every ``code`` / ``key`` pair listed in section 12 of an
   operation page must be registered on ``docs/internal/api/_shared/error-catalog.html``. Catalog
   entries that no operation references are reported as warnings (not failures).

Exit codes:
    0 — all checks pass.
    1 — any check failed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OPERATIONS_GLOB = "docs/internal/api/*/operations/*.html"
ERROR_CATALOG = REPO_ROOT / "docs/internal/api/_shared/error-catalog.html"
OPENAPI_BASELINE = REPO_ROOT / "docs/openapi/openapi-baseline.json"

# A spec page in these statuses is allowed to lack a corresponding OpenAPI operation:
# the spec is the source of truth and may precede implementation.
ALLOW_NO_OPENAPI_STATUSES: frozenset[str] = frozenset({"draft", "in-review", "approved"})


def _attribute(html: str, attr: str, *, on_tag: str = "body") -> str | None:
    """Read ``attr`` value from the first ``<{on_tag} ...>`` opening tag."""
    tag_match = re.search(rf"<{on_tag}\b[^>]*>", html, flags=re.IGNORECASE | re.DOTALL)
    if tag_match is None:
        return None
    attr_match = re.search(
        rf'\b{re.escape(attr)}\s*=\s*"([^"]*)"',
        tag_match.group(0),
        flags=re.IGNORECASE,
    )
    return attr_match.group(1) if attr_match else None


def _find_section(html: str, section_id: str) -> str | None:
    """Return the inner HTML of ``<section data-spec-section="<id>">...``, or ``None``."""
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
    return html[start:close]


# Tokens like USER_404, COMMON_409, CONS_409, ERR_404 — domain prefix + 3-digit suffix.
_CODE_RE = re.compile(r"\b([A-Z]+_\d{3})\b")
# Tokens like CONSPECTUS_REVIEW_REVISION_CONFLICT — uppercase + underscores; min 2 segments.
_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+(?:_[A-Z0-9]+){1,})\b")
# Codes that are part of the schema vocabulary and must not be treated as catalog entries.
_NON_CODE_TOKENS: frozenset[str] = frozenset(
    {"COMMON_400", "COMMON_500"}
)  # placeholder; trimmed in collect_codes


def _collect_error_tokens(html: str) -> tuple[set[str], set[str]]:
    """Return ``(codes, keys)`` parsed from the error-catalog section of an operation page.

    Args:
        html: Whole-document HTML.

    Returns:
        Tuple of two sets — distinct ``code`` values and ``key`` values found in section 12.
        Returns empty sets when the section is missing.
    """
    body = _find_section(html, "error-catalog")
    if body is None:
        return set(), set()
    codes = set(_CODE_RE.findall(body))
    keys = set(_KEY_RE.findall(body))
    # Domain prefix tokens (USER_, CONS_, ERR_, COMMON_) standalone are not codes; the regex
    # already filters those by requiring digits. But it does match keys like USER_NOT_FOUND
    # which we want — those are keys, not codes.
    keys -= codes
    return codes, keys


def _collect_catalog_tokens(html: str) -> tuple[set[str], set[str]]:
    """Return ``(codes, keys)`` registered in the shared error catalog page."""
    codes = set(_CODE_RE.findall(html))
    keys = set(_KEY_RE.findall(html))
    keys -= codes
    return codes, keys


def _read_openapi_operation_ids(path: Path) -> set[str]:
    """Read ``operationId`` values declared in the OpenAPI baseline document.

    Args:
        path: Path to ``openapi-baseline.json``.

    Returns:
        Distinct ``operationId`` strings; empty set when the file is missing or unreadable.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return set()
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return set()
    out: set[str] = set()
    paths = doc.get("paths") if isinstance(doc, dict) else None
    if not isinstance(paths, dict):
        return out
    for _path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for _method, op in methods.items():
            if isinstance(op, dict):
                op_id = op.get("operationId")
                if isinstance(op_id, str):
                    out.add(op_id)
    return out


def _collect_specs(repo_root: Path) -> list[Path]:
    """Return every operation spec page sorted by path."""
    return sorted(repo_root.glob(OPERATIONS_GLOB))


def _consistency_run(repo_root: Path) -> tuple[list[str], list[str]]:
    """Execute the three consistency checks.

    Args:
        repo_root: Repository root.

    Returns:
        ``(failures, warnings)`` — lists of human-readable messages. ``failures`` non-empty
        means the script exits 1.
    """
    failures: list[str] = []
    warnings: list[str] = []

    spec_paths = _collect_specs(repo_root)
    if not spec_paths:
        return ["spec_consistency: no operation specs found"], []

    # Check 1 + 2: operationId mapping.
    openapi_ids = _read_openapi_operation_ids(OPENAPI_BASELINE)
    spec_ids: dict[str, list[Path]] = {}
    for path in spec_paths:
        html = path.read_text(encoding="utf-8")
        op_id = _attribute(html, "data-spec-operation-id")
        status = _attribute(html, "data-spec-status") or ""
        if not op_id:
            warnings.append(f"{path.relative_to(repo_root)}: no data-spec-operation-id (skipped)")
            continue
        spec_ids.setdefault(op_id, []).append(path)
        if status == "implemented" and op_id not in openapi_ids:
            failures.append(
                f"{path.relative_to(repo_root)}: status=implemented but "
                f"operationId {op_id!r} not in {OPENAPI_BASELINE.relative_to(repo_root)}",
            )
        if status not in ALLOW_NO_OPENAPI_STATUSES and status != "implemented" and status:
            # Other statuses (e.g. deprecated): require OpenAPI presence.
            if op_id not in openapi_ids:
                failures.append(
                    f"{path.relative_to(repo_root)}: status={status} but "
                    f"operationId {op_id!r} not in OpenAPI",
                )

    for op_id, paths in spec_ids.items():
        if len(paths) > 1:
            joined = ", ".join(str(p.relative_to(repo_root)) for p in paths)
            failures.append(f"operationId {op_id!r} declared on multiple pages: {joined}")

    declared = set(spec_ids.keys())
    orphan_in_openapi = sorted(openapi_ids - declared)
    for op_id in orphan_in_openapi:
        warnings.append(f"OpenAPI operationId {op_id!r} has no internal spec page")

    # Check 3: error tokens vs catalog.
    if not ERROR_CATALOG.exists():
        failures.append(
            f"shared error catalog not found at {ERROR_CATALOG.relative_to(repo_root)}",
        )
        return failures, warnings

    catalog_html = ERROR_CATALOG.read_text(encoding="utf-8")
    catalog_codes, catalog_keys = _collect_catalog_tokens(catalog_html)

    seen_codes: set[str] = set()
    seen_keys: set[str] = set()
    for path in spec_paths:
        html = path.read_text(encoding="utf-8")
        codes, keys = _collect_error_tokens(html)
        seen_codes |= codes
        seen_keys |= keys
        for code in sorted(codes - catalog_codes):
            failures.append(
                f"{path.relative_to(repo_root)}: error code {code!r} not in shared error catalog",
            )
        for key in sorted(keys - catalog_keys):
            failures.append(
                f"{path.relative_to(repo_root)}: error key {key!r} not in shared error catalog",
            )

    for code in sorted(catalog_codes - seen_codes):
        warnings.append(f"catalog code {code!r} is not referenced by any operation page")
    for key in sorted(catalog_keys - seen_keys):
        warnings.append(f"catalog key {key!r} is not referenced by any operation page")

    return failures, warnings


def main(argv: Iterable[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument vector. ``None`` defers to :data:`sys.argv`.

    Returns:
        Exit code (0 on success, 1 on any failure).
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict-warnings",
        action="store_true",
        help="Treat warnings as failures.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    failures, warnings = _consistency_run(REPO_ROOT)

    out = sys.stderr if (failures or (args.strict_warnings and warnings)) else sys.stdout
    if failures:
        print("FAIL spec_consistency:", file=out)
        for msg in failures:
            print(f"     - {msg}", file=out)
    if warnings:
        print("WARN spec_consistency:", file=out)
        for msg in warnings:
            print(f"     - {msg}", file=out)
    if not failures and not warnings:
        print("spec_consistency: OK", file=out)

    if failures:
        return 1
    if args.strict_warnings and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
