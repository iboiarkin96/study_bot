"""Auto-generate documentation sections from code sources.

Reads the Makefile help target and FastAPI app routes, then patches
marker-delimited sections in README.md, docs/internal/system-design.html,
and docs/internal/developers.html.

Markers have the form:
    <!-- BEGIN:SECTION_NAME -->
    ...content replaced on every run...
    <!-- END:SECTION_NAME -->

Usage:
    python scripts/sync_docs.py          # one-shot sync
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NO_COLOR = os.getenv("NO_COLOR", "0") == "1"
COLOR_RESET = "" if NO_COLOR else "\033[0m"
COLOR_GREEN = "" if NO_COLOR else "\033[32m"
COLOR_CYAN = "" if NO_COLOR else "\033[36m"
ICON_OK = f"{COLOR_GREEN}✓{COLOR_RESET}"
ICON_STEP = f"{COLOR_CYAN}→{COLOR_RESET}"
ICON_INFO = "·"


def _ok(message: str) -> None:
    """Print a green success line to stdout.

    Args:
        message: Text after the checkmark icon.
    """
    print(f"{ICON_OK} {message}")


def _step(message: str) -> None:
    """Print a cyan progress line to stdout.

    Args:
        message: Text after the arrow icon.
    """
    print(f"{ICON_STEP} {message}")


def _info(message: str) -> None:
    """Print a neutral bullet line to stdout.

    Args:
        message: Informational text.
    """
    print(f"{ICON_INFO} {message}")


# ---------------------------------------------------------------------------
# Marker replacement engine
# ---------------------------------------------------------------------------

_MARKER_RE = re.compile(
    r"([ \t]*<!-- BEGIN:(\w+) -->)\n.*?\n([ \t]*<!-- END:\2 -->)",
    re.DOTALL,
)


def _replace_markers(text: str, sections: dict[str, str]) -> str:
    """Replace content between ``<!-- BEGIN:name -->`` / ``END`` pairs when ``name`` is in ``sections``.

    Args:
        text: Full file text containing marker pairs.
        sections: Map of marker name to replacement inner content (without markers).

    Returns:
        Text with matching sections substituted; unknown markers left unchanged.
    """

    def _sub(m: re.Match) -> str:
        """Substitute one regex match if the marker name exists in ``sections``."""
        name = m.group(2)
        if name in sections:
            return f"{m.group(1)}\n{sections[name]}\n{m.group(3)}"
        return m.group(0)

    return _MARKER_RE.sub(_sub, text)


# ---------------------------------------------------------------------------
# Makefile help parser
# ---------------------------------------------------------------------------

_HELP_LINE_RE = re.compile(
    r"make (\S+(?:\s+\w+=\S+)?)\s+(.+)",
)


def _parse_makefile_help() -> list[tuple[str, str]]:
    """Parse ``make help``-style echo lines from the root Makefile.

    Returns:
        Sorted list of ``(make_target, description)`` tuples; empty if Makefile missing.
    """
    makefile = ROOT / "Makefile"
    if not makefile.exists():
        return []

    entries_by_command: dict[str, str] = {}
    for line in makefile.read_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith('@echo "  make '):
            continue
        # strip @echo " and trailing "
        inner = stripped.removeprefix('@echo "').removesuffix('"').strip()
        m = _HELP_LINE_RE.match(inner)
        if m:
            command = m.group(1)
            description = m.group(2).strip()
            if description.startswith("#"):
                description = description.lstrip("#").strip()
            # Keep the most complete/authoritative description in case of duplicates.
            entries_by_command[command] = description
    return sorted(entries_by_command.items(), key=lambda item: item[0])


def _render_makefile_table(entries: list[tuple[str, str]]) -> str:
    """Build a GitHub-flavored markdown table of make commands.

    Args:
        entries: Rows from :func:`_parse_makefile_help`.

    Returns:
        Markdown string for README embedding.
    """
    rows = ["| Command | Purpose |", "| ------- | ------- |"]
    for cmd, desc in entries:
        rows.append(f"| `make {cmd}` | {desc} |")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# FastAPI route introspector
# ---------------------------------------------------------------------------


def _get_fastapi_routes() -> list[tuple[str, str, str]]:
    """Introspect registered :class:`fastapi.routing.APIRoute` entries on the app.

    Returns:
        Sorted list of ``(HTTP method, path, summary)``; empty if import fails.
    """
    sys.path.insert(0, str(ROOT))
    try:
        from app.main import app  # noqa: WPS433
    except Exception as exc:
        print(f"  ⚠ Could not import FastAPI app: {exc}", file=sys.stderr)
        return []

    from fastapi.routing import APIRoute

    routes: list[tuple[str, str, str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods):
            summary = route.summary or route.name.replace("_", " ").title()
            routes.append((method, route.path, summary))
    routes.sort(key=lambda r: (r[1], r[0]))
    return routes


def _render_endpoints_md(routes: list[tuple[str, str, str]]) -> str:
    """Render route list as a markdown table for README markers.

    Args:
        routes: Output of :func:`_get_fastapi_routes`.

    Returns:
        Markdown table string.
    """
    rows = ["| Method | Path | Description |", "| ------ | ---- | ----------- |"]
    for method, path, summary in routes:
        rows.append(f"| `{method}` | `{path}` | {summary} |")
    return "\n".join(rows)


def _render_endpoints_html(routes: list[tuple[str, str, str]]) -> str:
    """Render route list as HTML snippet for ``internal/system-design.html`` markers.

    Args:
        routes: Output of :func:`_get_fastapi_routes`.

    Returns:
        Indented HTML fragment.
    """
    lines = ['      <div class="card">']
    for method, path, summary in routes:
        lines.append(f'        <p><span class="badge">{method} {path}</span> {summary}</p>')
    lines.append("      </div>")
    return "\n".join(lines)


def _render_makefile_html(entries: list[tuple[str, str]]) -> str:
    """Build an HTML ``<table>`` of make commands for engineering practices page.

    Args:
        entries: Rows from :func:`_parse_makefile_help`.

    Returns:
        HTML table markup with escaped cells.
    """
    lines = [
        "          <table>",
        "            <thead>",
        "              <tr>",
        "                <th>Command</th>",
        "                <th>Purpose</th>",
        "              </tr>",
        "            </thead>",
        "            <tbody>",
    ]
    for command, description in entries:
        escaped_cmd = html.escape(f"make {command}")
        escaped_desc = html.escape(description)
        lines.extend(
            [
                "              <tr>",
                f"                <td><code>{escaped_cmd}</code></td>",
                f"                <td>{escaped_desc}</td>",
                "              </tr>",
            ]
        )
    lines.extend(["            </tbody>", "          </table>"])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Error catalog renderers (docs/internal/errors.html)
# ---------------------------------------------------------------------------


def _load_error_catalog() -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """Load stable error identities from ``app.errors`` modules.

    Returns:
        Two sorted lists of tuples ``(code, key, message)``:
        first for ``COMMON_*``, second for ``USER_*``.
    """
    sys.path.insert(0, str(ROOT))
    try:
        import app.errors.common as common_module  # noqa: WPS433
        import app.errors.user as user_module  # noqa: WPS433
        from app.errors.types import StableError  # noqa: WPS433
    except Exception as exc:
        print(f"  ⚠ Could not import error catalog: {exc}", file=sys.stderr)
        return [], []

    common_symbols = vars(common_module)
    common_rows: list[tuple[str, str, str]] = []
    for name, value in common_symbols.items():
        if not name.startswith("COMMON_") or not isinstance(value, StableError):
            continue
        common_rows.append((value.code, value.key, value.message))
    common_rows.sort(key=lambda row: row[0])

    user_symbols = vars(user_module)
    user_rows: list[tuple[str, str, str]] = []
    for name, value in user_symbols.items():
        if not name.startswith("USER_") or not isinstance(value, StableError):
            continue
        user_rows.append((value.code, value.key, value.message))
    user_rows.sort(key=lambda row: row[0])

    return common_rows, user_rows


def _load_validation_rule_rows() -> list[tuple[str, str, str, str, str]]:
    """Build rows for documented validation mapping dicts.

    Returns:
        Sorted list of ``(rule_set, field, pydantic_type, code, key)`` rows.
    """
    sys.path.insert(0, str(ROOT))
    try:
        from app.errors.user import (  # noqa: WPS433
            CREATE_USER_VALIDATION_RULES,
            UPDATE_USER_VALIDATION_RULES,
        )
    except Exception as exc:
        print(f"  ⚠ Could not import validation rules: {exc}", file=sys.stderr)
        return []

    rows: list[tuple[str, str, str, str, str]] = []
    for rule_set, mapping in (
        ("CREATE_USER_VALIDATION_RULES", CREATE_USER_VALIDATION_RULES),
        ("UPDATE_USER_VALIDATION_RULES", UPDATE_USER_VALIDATION_RULES),
    ):
        for (field, pydantic_type), err in mapping.items():
            rows.append((rule_set, field, pydantic_type, err.code, err.key))
    rows.sort(key=lambda row: (row[0], row[1], row[2], row[3]))
    return rows


def _render_error_rows_html(rows: list[tuple[str, str, str]], source_path: str) -> str:
    """Render ``(code, key, message)`` rows as HTML table body fragment.

    Args:
        rows: Error tuples loaded from code catalog modules.
        source_path: Relative path shown in the source column.

    Returns:
        HTML fragment with ``<tr>`` rows.
    """
    if not rows:
        return '                  <tr><td colspan="4"><em>No rows found.</em></td></tr>'

    out: list[str] = []
    for code, key, message in rows:
        out.extend(
            [
                "                  <tr>",
                f"                    <td><code>{html.escape(code)}</code></td>",
                f"                    <td><code>{html.escape(key)}</code></td>",
                f"                    <td>{html.escape(message)}</td>",
                f"                    <td><code>{html.escape(source_path)}</code></td>",
                "                  </tr>",
            ]
        )
    return "\n".join(out)


def _render_rule_rows_html(rows: list[tuple[str, str, str, str, str]]) -> str:
    """Render validation mapping rows as HTML fragment for docs marker.

    Args:
        rows: Tuples ``(rule_set, field, pydantic_type, code, key)``.

    Returns:
        HTML fragment with ``<tr>`` rows.
    """
    if not rows:
        return '                  <tr><td colspan="5"><em>No rows found.</em></td></tr>'

    out: list[str] = []
    for rule_set, field, pydantic_type, code, key in rows:
        out.extend(
            [
                "                  <tr>",
                f"                    <td><code>{html.escape(rule_set)}</code></td>",
                f"                    <td><code>{html.escape(field)}</code></td>",
                f"                    <td><code>{html.escape(pydantic_type)}</code></td>",
                f"                    <td><code>{html.escape(code)}</code></td>",
                f"                    <td><code>{html.escape(key)}</code></td>",
                "                  </tr>",
            ]
        )
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Documentation catalog for handbook table
# ---------------------------------------------------------------------------


def _extract_html_title(path: Path) -> str:
    """Read ``<title>`` from an HTML file, with light normalization and prefix stripping.

    Args:
        path: HTML document path.

    Returns:
        Title text, or stem of filename if no title tag.
    """
    text = path.read_text()
    m = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    if not m:
        return path.stem
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    if title.startswith("ETR Study API — "):
        return title.removeprefix("ETR Study API — ").strip()
    return title


def _doc_sort_key(path: Path) -> tuple[int, str]:
    """Sort key: README first, then ``0000-*`` templates, then others alphabetically.

    Args:
        path: HTML file in a handbook directory.

    Returns:
        Tuple used with ``sorted(..., key=)``.
    """
    name = path.name
    if name == "README.html":
        return (0, "")
    if name.startswith("0000-"):
        return (1, name)
    return (2, name)


_HANDBOOK_EXCLUDE_PREFIXES: tuple[str, ...] = ("draft-",)
_HANDBOOK_EXCLUDE_SUBSTRINGS: tuple[str, ...] = ("-draft-", "_draft", ".draft.")

_HANDBOOK_EXCLUDE_EXACT: frozenset[str] = frozenset(
    {
        # Canonical page is docs/howto/0004-…; keep a redirect stub under developer/ for old links.
        "developer/0004-how-to-add-post-contract.html",
    }
)


def _should_include_handbook_doc(path: Path) -> bool:
    """Return False for draft or excluded handbook pages.

    Args:
        path: Candidate HTML file under ``docs/``.

    Returns:
        Whether the file should appear in the handbook table of contents.
    """
    name = path.name.lower()
    stem = path.stem.lower()
    if any(name.startswith(prefix) for prefix in _HANDBOOK_EXCLUDE_PREFIXES):
        return False
    if any(token in name for token in _HANDBOOK_EXCLUDE_SUBSTRINGS):
        return False
    if stem.endswith("-draft") or stem.endswith("_draft"):
        return False
    try:
        rel_key = path.relative_to(ROOT / "docs").as_posix()
    except ValueError:
        return True
    if rel_key in _HANDBOOK_EXCLUDE_EXACT:
        return False
    return True


_HANDBOOK_DESCRIPTION_OVERRIDES: dict[str, str] = {
    "internal/system-design.html": "System design: context, FR/NFR, architecture, API contracts, and diagrams.",
    "internal/developers.html": "Developers Docs: engineering workflow, policies, quality gates, and developer guides index.",
    "developer/0001-requirements.html": "Developer interpretation of requirements and done criteria.",
    "developer/0002-schemas-and-contracts.html": (
        "Rules for request/response/error contracts and backward-compatible changes."
    ),
    "developer/0003-business-logic.html": "Layer responsibilities and implementation change flow.",
    "howto/README.html": (
        "How-to index: internal HTML documentation layout and endpoint walkthroughs (moved from STRUCTURE.md and developer/0004)."
    ),
    "howto/internal-service-docs-layout.html": (
        "Directory layout for docs/internal/, shared chrome, and how to add or edit resource and operation pages."
    ),
    "howto/0004-how-to-add-post-contract.html": (
        "Step-by-step guide for adding POST /api/v1/contract."
    ),
    "developer/0007-local-development.html": (
        "Local run targets (make run, make run-project), observability stack, ports, and shutdown."
    ),
    "adr/0005-api-security-defaults.html": (
        "Security-by-default policy for auth, rate-limit, CORS, headers, and body-size limits."
    ),
    "adr/0006-idempotency-write-operations.html": (
        "Idempotency contract for write operations using Idempotency-Key and dedup behavior."
    ),
    "runbooks/0006-api-security-failing.html": (
        "Incident recovery for auth failures, rate-limit spikes, CORS issues, and "
        "security headers/body limits."
    ),
}


def _handbook_doc_entries() -> list[tuple[str, str, str, str]]:
    """Build rows for the handbook documentation table (title, desc, href, link label).

    Returns:
        List of tuples for :func:`_render_handbook_rows_html`.
    """
    docs = ROOT / "docs"
    entries: list[tuple[str, str, str, str]] = []

    fixed_root = [
        docs / "internal" / "system-design.html",
        docs / "internal" / "developers.html",
    ]
    for path in fixed_root:
        if not path.exists():
            continue
        title = _extract_html_title(path)
        rel_key = path.relative_to(docs).as_posix()
        desc = _HANDBOOK_DESCRIPTION_OVERRIDES.get(
            rel_key, "Project-level architecture and governance document."
        )
        open_label = "Open document"
        entries.append((title, desc, f"./{rel_key}", open_label))

    grouped_dirs = [
        (
            "Developer Docs",
            docs / "developer",
            "developer guide",
            "Open guide",
            "Developer Docs Template",
            "Entry point for all developer guides.",
        ),
        (
            "How-to guides",
            docs / "howto",
            "how-to guide",
            "Open guide",
            "How-to Template",
            "Task-focused guides for internal HTML docs and endpoint implementation.",
        ),
        (
            "ADR",
            docs / "adr",
            "architecture decision record",
            "Open ADR",
            "ADR Template",
            "Architecture and policy decisions with rationale and references.",
        ),
        (
            "Runbooks",
            docs / "runbooks",
            "operational runbook",
            "Open runbook",
            "Runbook Template",
            "Operational incident guides and standardized recovery checklists.",
        ),
    ]
    for (
        group_name,
        directory,
        generic_kind,
        open_label,
        template_title,
        index_description,
    ) in grouped_dirs:
        if not directory.exists():
            continue
        html_files = sorted(
            (path for path in directory.glob("*.html") if _should_include_handbook_doc(path)),
            key=_doc_sort_key,
        )
        for path in html_files:
            rel = f"./{path.relative_to(docs).as_posix()}"
            rel_key = path.relative_to(docs).as_posix()
            if path.name == "README.html":
                title = f"{group_name} Index"
                desc = index_description
                entries.append((title, desc, rel, "Open index"))
                continue
            if path.name.startswith("0000-"):
                title = template_title
                desc = f"Template for creating a new {generic_kind}."
                entries.append((title, desc, rel, "Open template"))
                continue

            title = _extract_html_title(path)
            desc = _HANDBOOK_DESCRIPTION_OVERRIDES.get(rel_key, f"Project {generic_kind}.")
            entries.append((title, desc, rel, open_label))

    return entries


def _render_handbook_rows_html(entries: list[tuple[str, str, str, str]]) -> str:
    """Render handbook rows as ``<tr>`` elements with escaped text.

    Args:
        entries: Rows from :func:`_handbook_doc_entries`.

    Returns:
        Concatenated HTML table rows.
    """
    lines: list[str] = []
    for title, description, href, open_label in entries:
        lines.extend(
            [
                "              <tr>",
                f"                <td>{html.escape(title)}</td>",
                f"                <td>{html.escape(description)}</td>",
                f'                <td><a href="{html.escape(href)}">{html.escape(open_label)}</a></td>',
                "              </tr>",
            ]
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Repository layout tree
# ---------------------------------------------------------------------------

_SKIP_DIRS = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    ".cursor",
    "node_modules",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".tox",
    ".nox",
    ".eggs",
    "htmlcov",
}

# Show only high-level architecture blocks at repository root.
_ARCHITECTURE_ROOT_DIRS = ("app", "alembic", "docs", "ops", "scripts")

# Default depth is 2 (root + one nested level), but some domains are worth 3.
_MAX_DEPTH_DEFAULT = 2
_MAX_DEPTH_BY_ROOT = {
    "app": 3,
    "docs": 3,
}

_DIR_COMMENTS: dict[str, str] = {
    "app": "Application package",
    "app/api": "HTTP layer",
    "app/api/v1": "v1 routers",
    "app/core": "Settings, DB session",
    "app/models": "ORM models",
    "app/models/core": "Core domain entities",
    "app/models/reference": "Reference / lookup entities",
    "app/repositories": "Data-access layer",
    "app/schemas": "Pydantic request/response models",
    "app/services": "Business logic",
    "alembic": "Migration environment",
    "alembic/versions": "Migration scripts",
    "docs": "HTML docs & UML sources",
    "docs/developer": "Developer guides and onboarding",
    "docs/runbooks": "Operational troubleshooting guides",
    "docs/uml": "PlantUML diagrams",
    "docs/uml/include": "Shared PlantUML skin (merged at Kroki render)",
    "docs/uml/sequences": "Sequence diagram sources",
    "docs/uml/rendered": "Rendered SVGs",
    "ops": "Prometheus, Grafana, Filebeat configs",
    "ops/filebeat": "Filebeat → Elasticsearch (local logging stack)",
    "ops/grafana": "Dashboards and provisioning",
    "ops/prometheus": "Scrape config, rules, Blackbox",
    "scripts": "Dev & CI helper scripts",
}


def _build_tree() -> str:
    """Build a fenced code block showing a small directory tree of key project folders.

    Returns:
        Markdown code block string for the ``REPO_LAYOUT`` marker.
    """

    lines: list[str] = [f"{ROOT.name}/"]

    _ROOT_FILE_COMMENTS: tuple[tuple[str, str], ...] = (
        ("docker-compose.observability.yml", "Prometheus, Grafana, Blackbox"),
        ("docker-compose.logging.yml", "Optional: Elasticsearch, Kibana, Filebeat"),
    )
    for fname, comment in _ROOT_FILE_COMMENTS:
        if (ROOT / fname).is_file():
            lines.append(f"├── {fname}  # {comment}")

    def _walk(directory: Path, prefix: str, rel: str, max_depth: int) -> None:
        """Recursively append directory lines up to ``max_depth`` relative to ``rel``.

        Args:
            directory: Current directory to list.
            prefix: ASCII tree prefix for this depth.
            rel: POSIX path relative to repo root for comment lookup.
            max_depth: Maximum number of path segments below root to show.
        """
        current_depth = len(rel.split("/")) if rel else 0
        if current_depth >= max_depth:
            return

        entries = sorted(
            [
                child
                for child in directory.iterdir()
                if child.is_dir() and child.name not in _SKIP_DIRS
            ],
            key=lambda p: p.name,
        )

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            child_rel = f"{rel}/{entry.name}" if rel else entry.name
            comment = _DIR_COMMENTS.get(child_rel, "")
            suffix = f"  # {comment}" if comment else ""
            lines.append(f"{prefix}{connector}{entry.name}/{suffix}")
            extension = "    " if is_last else "│   "
            _walk(entry, prefix + extension, child_rel, max_depth)

    existing_roots = [ROOT / name for name in _ARCHITECTURE_ROOT_DIRS if (ROOT / name).is_dir()]
    for i, directory in enumerate(existing_roots):
        is_last = i == len(existing_roots) - 1
        connector = "└── " if is_last else "├── "
        rel = directory.name
        comment = _DIR_COMMENTS.get(rel, "")
        suffix = f"  # {comment}" if comment else ""
        lines.append(f"{connector}{directory.name}/{suffix}")
        extension = "    " if is_last else "│   "
        max_depth = _MAX_DEPTH_BY_ROOT.get(directory.name, _MAX_DEPTH_DEFAULT)
        _walk(directory, extension, rel, max_depth)

    return "```text\n" + "\n".join(lines) + "\n```"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def sync(check: bool = False) -> int:
    """Regenerate marker-delimited sections in README and HTML docs from live sources.

    Args:
        check: If True, do not write files; only count how many would change.

    Returns:
        Number of files that would be or were updated (stale count).
    """
    _step("Syncing docs from code sources...")
    makefile_entries = _parse_makefile_help()
    routes = _get_fastapi_routes()
    common_errors, user_errors = _load_error_catalog()
    rule_rows = _load_validation_rule_rows()
    stale_files = 0

    repo_layout = _build_tree()

    # --- README.md ---
    readme_path = ROOT / "README.md"
    if readme_path.exists():
        readme_sections: dict[str, str] = {}
        readme_sections["REPO_LAYOUT"] = repo_layout
        if makefile_entries:
            readme_sections["MAKEFILE_REF"] = _render_makefile_table(makefile_entries)
        if routes:
            readme_sections["HTTP_ENDPOINTS"] = _render_endpoints_md(routes)

        original = readme_path.read_text()
        updated = _replace_markers(original, readme_sections)
        if updated != original:
            stale_files += 1
            if check:
                print("✗ README.md is out of sync (run make docs-fix)")
            else:
                readme_path.write_text(updated)
                _ok("README.md updated")
        else:
            _info("README.md already up to date")

    # --- docs/internal/system-design.html ---
    html_path = ROOT / "docs" / "internal" / "system-design.html"
    if html_path.exists():
        html_sections: dict[str, str] = {}
        if routes:
            html_sections["API_CONTRACTS"] = _render_endpoints_html(routes)

        original = html_path.read_text()
        updated = _replace_markers(original, html_sections)
        if updated != original:
            stale_files += 1
            if check:
                print("✗ docs/internal/system-design.html is out of sync (run make docs-fix)")
            else:
                html_path.write_text(updated)
                _ok("docs/internal/system-design.html updated")
        else:
            _info("docs/internal/system-design.html already up to date")

    # --- docs/internal/developers.html (Developers Docs: Makefile table sync) ---
    eng_path = ROOT / "docs" / "internal" / "developers.html"
    if eng_path.exists():
        eng_sections: dict[str, str] = {}
        if makefile_entries:
            eng_sections["MAKEFILE_COMMANDS"] = _render_makefile_html(makefile_entries)
        handbook_entries = _handbook_doc_entries()
        if handbook_entries:
            eng_sections["HANDBOOK_DOC_ROWS"] = _render_handbook_rows_html(handbook_entries)

        original = eng_path.read_text()
        updated = _replace_markers(original, eng_sections)
        if updated != original:
            stale_files += 1
            if check:
                print("✗ docs/internal/developers.html is out of sync (run make docs-fix)")
            else:
                eng_path.write_text(updated)
                _ok("docs/internal/developers.html updated")
        else:
            _info("docs/internal/developers.html already up to date")

    # --- docs/internal/api/errors.html (error catalog sync) ---
    errors_path = ROOT / "docs" / "internal" / "api" / "errors.html"
    if errors_path.exists():
        errors_sections: dict[str, str] = {
            "ERROR_COMMON_ROWS": _render_error_rows_html(common_errors, "app/errors/common.py"),
            "ERROR_USER_ROWS": _render_error_rows_html(user_errors, "app/errors/user.py"),
            "ERROR_RULE_ROWS": _render_rule_rows_html(rule_rows),
        }

        original = errors_path.read_text()
        updated = _replace_markers(original, errors_sections)
        if updated != original:
            stale_files += 1
            if check:
                print("✗ docs/internal/api/errors.html is out of sync (run make docs-fix)")
            else:
                errors_path.write_text(updated)
                _ok("docs/internal/api/errors.html updated")
        else:
            _info("docs/internal/api/errors.html already up to date")
    return stale_files


def main() -> None:
    """CLI: run :func:`sync` with optional ``--check`` (exit 1 if stale in check mode)."""
    parser = argparse.ArgumentParser(description="Sync docs from source code.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check docs are in sync without modifying files.",
    )
    args = parser.parse_args()
    stale = sync(check=args.check)
    if args.check and stale:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
