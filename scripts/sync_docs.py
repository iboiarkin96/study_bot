"""Auto-generate documentation sections from code sources.

Reads the Makefile help target, FastAPI app routes, and .env.example,
then patches marker-delimited sections in README.md, docs/system-analysis.html,
and docs/engineering-practices.html.

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
    print(f"{ICON_OK} {message}")


def _step(message: str) -> None:
    print(f"{ICON_STEP} {message}")


def _info(message: str) -> None:
    print(f"{ICON_INFO} {message}")


# ---------------------------------------------------------------------------
# Marker replacement engine
# ---------------------------------------------------------------------------

_MARKER_RE = re.compile(
    r"([ \t]*<!-- BEGIN:(\w+) -->)\n.*?\n([ \t]*<!-- END:\2 -->)",
    re.DOTALL,
)


def _replace_markers(text: str, sections: dict[str, str]) -> str:
    """Replace content between BEGIN/END markers with generated text."""

    def _sub(m: re.Match) -> str:
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
    """Extract (command, description) pairs from the help target echo lines."""
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
    rows = ["| Command | Purpose |", "| ------- | ------- |"]
    for cmd, desc in entries:
        rows.append(f"| `make {cmd}` | {desc} |")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# FastAPI route introspector
# ---------------------------------------------------------------------------


def _get_fastapi_routes() -> list[tuple[str, str, str]]:
    """Return (method, path, summary) for every route registered on the app."""
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
    rows = ["| Method | Path | Description |", "| ------ | ---- | ----------- |"]
    for method, path, summary in routes:
        rows.append(f"| `{method}` | `{path}` | {summary} |")
    return "\n".join(rows)


def _render_endpoints_html(routes: list[tuple[str, str, str]]) -> str:
    lines = ['      <div class="card">']
    for method, path, summary in routes:
        lines.append(f'        <p><span class="badge">{method} {path}</span> {summary}</p>')
    lines.append("      </div>")
    return "\n".join(lines)


def _render_makefile_html(entries: list[tuple[str, str]]) -> str:
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
# Documentation catalog for handbook table
# ---------------------------------------------------------------------------


def _extract_html_title(path: Path) -> str:
    text = path.read_text()
    m = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    if not m:
        return path.stem
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    if title.startswith("ETR Study API — "):
        return title.removeprefix("ETR Study API — ").strip()
    return title


def _doc_sort_key(path: Path) -> tuple[int, str]:
    name = path.name
    if name == "README.html":
        return (0, "")
    if name.startswith("0000-"):
        return (1, name)
    return (2, name)


_HANDBOOK_EXCLUDE_PREFIXES: tuple[str, ...] = ("draft-",)
_HANDBOOK_EXCLUDE_SUBSTRINGS: tuple[str, ...] = ("-draft-", "_draft", ".draft.")


def _should_include_handbook_doc(path: Path) -> bool:
    name = path.name.lower()
    stem = path.stem.lower()
    if any(name.startswith(prefix) for prefix in _HANDBOOK_EXCLUDE_PREFIXES):
        return False
    if any(token in name for token in _HANDBOOK_EXCLUDE_SUBSTRINGS):
        return False
    if stem.endswith("-draft") or stem.endswith("_draft"):
        return False
    return True


_HANDBOOK_DESCRIPTION_OVERRIDES: dict[str, str] = {
    "system-analysis.html": "Analyst document with context, FR/NFR, architecture, API contracts, and diagrams.",
    "engineering-practices.html": "Engineering workflow, delivery policies, and quality gates.",
    "developer/0001-requirements.html": "Developer interpretation of requirements and done criteria.",
    "developer/0002-schemas-and-contracts.html": (
        "Rules for request/response/error contracts and backward-compatible changes."
    ),
    "developer/0003-business-logic.html": "Layer responsibilities and implementation change flow.",
    "developer/0004-how-to-add-post-contract.html": (
        "Step-by-step guide for adding POST /api/v1/contract."
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
    docs = ROOT / "docs"
    entries: list[tuple[str, str, str, str]] = []

    fixed_root = [
        docs / "system-analysis.html",
        docs / "engineering-practices.html",
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
        entries.append((title, desc, f"./{path.name}", open_label))

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
# .env.example parser
# ---------------------------------------------------------------------------

_ENV_LINE_RE = re.compile(r"^([A-Z_]+)=(.*)$")


def _parse_env_example() -> list[tuple[str, str]]:
    """Return (variable, example_value) pairs from .env.example."""
    path = ROOT / ".env.example"
    if not path.exists():
        return []
    entries: list[tuple[str, str]] = []
    for line in path.read_text().splitlines():
        m = _ENV_LINE_RE.match(line.strip())
        if m:
            entries.append((m.group(1), m.group(2)))
    return entries


_CONFIG_DESCRIPTIONS: dict[str, str] = {
    "APP_NAME": "Title shown in OpenAPI",
    "APP_ENV": "Logical environment label",
    "APP_HOST": "Bind address for Uvicorn",
    "APP_PORT": "Listen port",
    "SQLITE_DB_PATH": "SQLite database file (relative or absolute path)",
    "LOG_DIR": "Directory where app logs are written",
    "LOG_FILE_NAME": "Application log filename",
    "LOG_LEVEL": "Root log level",
    "CORS_ALLOW_ORIGINS": "Allowed browser origins (CSV)",
    "CORS_ALLOW_METHODS": "Allowed CORS methods (CSV)",
    "CORS_ALLOW_HEADERS": "Allowed CORS headers (CSV)",
    "CORS_ALLOW_CREDENTIALS": "Whether CORS credentials are allowed",
    "API_BODY_MAX_BYTES": "Maximum request body size in bytes",
    "API_RATE_LIMIT_REQUESTS": "Requests per window for one client+path",
    "API_RATE_LIMIT_WINDOW_SECONDS": "Rate-limit window in seconds",
    "API_AUTH_STRATEGY": "Auth mode (`mock_api_key` or `disabled`)",
    "API_MOCK_API_KEY": "Mock API key value for local/dev",
    "API_AUTH_HEADER": "Header name used for API key auth",
    "API_PROTECTED_PREFIX": "URL prefix where auth/rate-limit are enforced",
}


def _render_config_table(entries: list[tuple[str, str]]) -> str:
    rows = [
        "| Variable | Description | Example |",
        "| -------- | ----------- | ------- |",
    ]
    for var, val in entries:
        desc = _CONFIG_DESCRIPTIONS.get(var, "")
        rows.append(f"| `{var}` | {desc} | `{val}` |")
    return "\n".join(rows)


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
_ARCHITECTURE_ROOT_DIRS = ("app", "alembic", "docs", "scripts")

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
    "docs/uml/sequences": "Sequence diagram sources",
    "docs/uml/rendered": "Rendered PNGs",
    "scripts": "Dev & CI helper scripts",
}


def _build_tree() -> str:
    """Render a concise architecture tree with directories only."""

    lines: list[str] = [f"{ROOT.name}/"]

    def _walk(directory: Path, prefix: str, rel: str, max_depth: int) -> None:
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
    _step("Syncing docs from code sources...")
    makefile_entries = _parse_makefile_help()
    routes = _get_fastapi_routes()
    env_entries = _parse_env_example()
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
        if env_entries:
            readme_sections["CONFIG_TABLE"] = _render_config_table(env_entries)

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

    # --- docs/system-analysis.html ---
    html_path = ROOT / "docs" / "system-analysis.html"
    if html_path.exists():
        html_sections: dict[str, str] = {}
        if routes:
            html_sections["API_CONTRACTS"] = _render_endpoints_html(routes)

        original = html_path.read_text()
        updated = _replace_markers(original, html_sections)
        if updated != original:
            stale_files += 1
            if check:
                print("✗ docs/system-analysis.html is out of sync (run make docs-fix)")
            else:
                html_path.write_text(updated)
                _ok("docs/system-analysis.html updated")
        else:
            _info("docs/system-analysis.html already up to date")

    # --- docs/engineering-practices.html ---
    eng_path = ROOT / "docs" / "engineering-practices.html"
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
                print("✗ docs/engineering-practices.html is out of sync (run make docs-fix)")
            else:
                eng_path.write_text(updated)
                _ok("docs/engineering-practices.html updated")
        else:
            _info("docs/engineering-practices.html already up to date")
    return stale_files


if __name__ == "__main__":
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
