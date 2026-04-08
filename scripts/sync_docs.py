"""Auto-generate documentation sections from code sources.

Reads the Makefile help target, FastAPI app routes, and .env.example,
then patches marker-delimited sections in README.md and docs/index.html.

Markers have the form:
    <!-- BEGIN:SECTION_NAME -->
    ...content replaced on every run...
    <!-- END:SECTION_NAME -->

Usage:
    python scripts/sync_docs.py          # one-shot sync
"""

from __future__ import annotations

import re
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[32m"
COLOR_CYAN = "\033[36m"
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

    entries: list[tuple[str, str]] = []
    for line in makefile.read_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith('@echo "  make '):
            continue
        # strip @echo " and trailing "
        inner = stripped.removeprefix('@echo "').removesuffix('"').strip()
        m = _HELP_LINE_RE.match(inner)
        if m:
            entries.append((m.group(1), m.group(2)))
    return entries


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
        lines.append(
            f'        <p><span class="badge">{method} {path}</span> {summary}</p>'
        )
    lines.append("      </div>")
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
    ".venv", "venv", "__pycache__", ".git", ".cursor",
    "node_modules", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    ".tox", ".nox", ".eggs", "htmlcov",
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
    "app":                "Application package",
    "app/api":            "HTTP layer",
    "app/api/v1":         "v1 routers",
    "app/core":           "Settings, DB session",
    "app/models":         "ORM models",
    "app/models/core":    "Core domain entities",
    "app/models/reference": "Reference / lookup entities",
    "app/repositories":   "Data-access layer",
    "app/schemas":        "Pydantic request/response models",
    "app/services":       "Business logic",
    "alembic":            "Migration environment",
    "alembic/versions":   "Migration scripts",
    "docs":               "HTML docs & UML sources",
    "docs/uml":           "PlantUML diagrams",
    "docs/uml/sequences": "Sequence diagram sources",
    "docs/uml/rendered":  "Rendered PNGs",
    "scripts":            "Dev & CI helper scripts",
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
                child for child in directory.iterdir()
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
                print("✗ README.md is out of sync (run make sync-docs)")
            else:
                readme_path.write_text(updated)
                _ok("README.md updated")
        else:
            _info("README.md already up to date")

    # --- docs/index.html ---
    html_path = ROOT / "docs" / "index.html"
    if html_path.exists():
        html_sections: dict[str, str] = {}
        if routes:
            html_sections["API_CONTRACTS"] = _render_endpoints_html(routes)

        original = html_path.read_text()
        updated = _replace_markers(original, html_sections)
        if updated != original:
            stale_files += 1
            if check:
                print("✗ docs/index.html is out of sync (run make sync-docs)")
            else:
                html_path.write_text(updated)
                _ok("docs/index.html updated")
        else:
            _info("docs/index.html already up to date")
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
