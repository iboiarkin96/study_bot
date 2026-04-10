"""Regenerate rendered UML diagrams for project documentation.

Usage:
  python scripts/regenerate_docs.py
  python scripts/regenerate_docs.py --watch
"""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UML_SRC_DIR = PROJECT_ROOT / "docs" / "uml"
UML_OUT_DIR = PROJECT_ROOT / "docs" / "uml" / "rendered"
KROKI_URL = "https://kroki.io/plantuml/png"
NO_COLOR = os.getenv("NO_COLOR", "0") == "1"
COLOR_RESET = "" if NO_COLOR else "\033[0m"
COLOR_GREEN = "" if NO_COLOR else "\033[32m"
COLOR_CYAN = "" if NO_COLOR else "\033[36m"
ICON_OK = f"{COLOR_GREEN}✓{COLOR_RESET}"
ICON_STEP = f"{COLOR_CYAN}→{COLOR_RESET}"


def _ok(message: str) -> None:
    """Print a green checkmark prefixed line to stdout.

    Args:
        message: Status text after the icon.
    """
    print(f"{ICON_OK} {message}")


def _step(message: str) -> None:
    """Print a cyan arrow prefixed line to stdout.

    Args:
        message: Progress or informational text.
    """
    print(f"{ICON_STEP} {message}")


def _source_files() -> list[Path]:
    """Collect every ``*.puml`` under ``docs/uml`` except files inside ``rendered/``.

    Returns:
        Sorted list of source paths.
    """
    files = sorted(UML_SRC_DIR.rglob("*.puml"))
    return [f for f in files if "rendered" not in f.parts]


def _output_for(source_path: Path) -> Path:
    """Map a ``.puml`` path to the PNG path under ``docs/uml/rendered``.

    Args:
        source_path: Absolute path to a PlantUML file.

    Returns:
        Destination PNG path (sequence diagrams keep stem-only names).
    """
    rel = source_path.relative_to(UML_SRC_DIR)
    # Keep legacy names for sequence diagrams to avoid breaking docs/system-analysis.html.
    if rel.parts and rel.parts[0] == "sequences":
        safe_name = source_path.stem + ".png"
    else:
        # Keep filenames stable and unique across non-sequence subdirectories.
        safe_name = "__".join(rel.with_suffix("").parts) + ".png"
    return UML_OUT_DIR / safe_name


def render_one(source_path: Path, output_path: Path) -> None:
    """Render one PlantUML file to PNG via POST to :data:`KROKI_URL` using ``curl``.

    Args:
        source_path: Input ``.puml`` file.
        output_path: Target ``.png`` path (parent dirs created).

    Raises:
        subprocess.CalledProcessError: If ``curl`` exits non-zero.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "curl",
        "-k",
        "-sS",
        "-X",
        "POST",
        "-H",
        "Content-Type: text/plain",
        "--data-binary",
        f"@{source_path}",
        KROKI_URL,
        "-o",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)


def render_all(verbose: bool = True) -> int:
    """Render every discovered PlantUML source to its PNG under ``rendered/``.

    Args:
        verbose: When True, print one success line per file via :func:`_ok`.

    Returns:
        Count of source files processed.
    """
    files = _source_files()
    for src in files:
        out = _output_for(src)
        render_one(src, out)
        if verbose:
            _ok(f"Rendered {out.relative_to(PROJECT_ROOT)}")
    return len(files)


def _is_render_up_to_date(source_path: Path, output_path: Path) -> bool:
    """Return True if re-rendering ``source_path`` yields byte-identical ``output_path``.

    Args:
        source_path: PlantUML input.
        output_path: Existing PNG to compare.

    Returns:
        Whether the on-disk PNG matches a fresh Kroki render.
    """
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        temp_path = Path(tmp.name)
    try:
        render_one(source_path, temp_path)
        if not output_path.exists():
            return False
        return temp_path.read_bytes() == output_path.read_bytes()
    finally:
        temp_path.unlink(missing_ok=True)


def check_all(verbose: bool = True) -> int:
    """Compare each source PNG pair without writing to the final path (except temp).

    Args:
        verbose: Print per-file status lines.

    Returns:
        Number of diagrams whose output is missing or differs from a fresh render.
    """
    stale = 0
    files = _source_files()
    for src in files:
        out = _output_for(src)
        if _is_render_up_to_date(src, out):
            if verbose:
                _ok(f"Up to date {out.relative_to(PROJECT_ROOT)}")
        else:
            stale += 1
            if verbose:
                print(f"✗ Stale {out.relative_to(PROJECT_ROOT)}")
    return stale


def watch(interval_sec: float = 1.0) -> None:
    """Poll ``*.puml`` files on an interval; rerender and delete outputs when sources change.

    Args:
        interval_sec: Sleep between polling loops (seconds).

    Note:
        Runs until the process is interrupted; performs an initial full render first.
    """
    _step("Watch mode enabled: monitoring docs/uml/**/*.puml")
    mtimes: dict[Path, float] = {}
    for src in _source_files():
        mtimes[src] = src.stat().st_mtime

    total = render_all(verbose=True)
    _ok(f"Initial render done: {total} file(s)")

    while True:
        changed = []
        current_files = _source_files()
        for src in current_files:
            mtime = src.stat().st_mtime
            if src not in mtimes or mtimes[src] != mtime:
                changed.append(src)
                mtimes[src] = mtime

        for src in changed:
            out = _output_for(src)
            render_one(src, out)
            _ok(f"Updated {out.relative_to(PROJECT_ROOT)}")

        removed = [path for path in mtimes if path not in current_files]
        for path in removed:
            mtimes.pop(path, None)
            out = _output_for(path)
            if out.exists():
                out.unlink()
                _step(f"Removed {out.relative_to(PROJECT_ROOT)}")

        time.sleep(interval_sec)


def main() -> None:
    """Parse CLI flags and either render all diagrams, check freshness, or watch sources."""
    parser = argparse.ArgumentParser(description="Regenerate UML diagrams for docs.")
    parser.add_argument(
        "--watch", action="store_true", help="Watch source files and rerender on changes."
    )
    parser.add_argument(
        "--interval", type=float, default=1.0, help="Watch polling interval in seconds."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check outputs are up-to-date without writing files.",
    )
    args = parser.parse_args()

    if args.watch:
        watch(interval_sec=args.interval)
        return

    if args.check:
        _step("Checking rendered UML outputs...")
        stale = check_all(verbose=True)
        if stale:
            print(f"✗ UML outputs are stale: {stale} file(s) need regeneration.")
            raise SystemExit(1)
        _ok("All rendered UML outputs are up to date")
        return

    _step("Rendering UML diagrams...")
    total = render_all(verbose=True)
    _ok(f"Done: rendered {total} file(s)")


if __name__ == "__main__":
    main()
