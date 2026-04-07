"""Regenerate rendered UML diagrams for project documentation.

Usage:
  python docs/regenerate_docs.py
  python docs/regenerate_docs.py --watch
"""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEQUENCE_SRC_DIR = PROJECT_ROOT / "docs" / "uml" / "sequences"
SEQUENCE_OUT_DIR = PROJECT_ROOT / "docs" / "uml" / "rendered"
KROKI_URL = "https://kroki.io/plantuml/png"


def render_one(source_path: Path, output_path: Path) -> None:
    """Render one PlantUML file to PNG using Kroki via curl."""
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
    """Render all sequence diagrams and return number of files."""
    files = sorted(SEQUENCE_SRC_DIR.glob("*.puml"))
    for src in files:
        out = SEQUENCE_OUT_DIR / f"{src.stem}.png"
        render_one(src, out)
        if verbose:
            print(f"rendered: {out.relative_to(PROJECT_ROOT)}")
    return len(files)


def watch(interval_sec: float = 1.0) -> None:
    """Watch sequence source files and rerender changed ones."""
    print("watch mode enabled: monitoring docs/uml/sequences/*.puml")
    mtimes: dict[Path, float] = {}
    for src in sorted(SEQUENCE_SRC_DIR.glob("*.puml")):
        mtimes[src] = src.stat().st_mtime

    # Initial full render.
    total = render_all(verbose=True)
    print(f"initial render done: {total} file(s)")

    while True:
        changed = []
        current_files = sorted(SEQUENCE_SRC_DIR.glob("*.puml"))
        for src in current_files:
            mtime = src.stat().st_mtime
            if src not in mtimes or mtimes[src] != mtime:
                changed.append(src)
                mtimes[src] = mtime

        for src in changed:
            out = SEQUENCE_OUT_DIR / f"{src.stem}.png"
            render_one(src, out)
            print(f"updated: {out.relative_to(PROJECT_ROOT)}")

        # Handle removed files in source directory.
        removed = [path for path in mtimes if path not in current_files]
        for path in removed:
            mtimes.pop(path, None)
            out = SEQUENCE_OUT_DIR / f"{path.stem}.png"
            if out.exists():
                out.unlink()
                print(f"removed: {out.relative_to(PROJECT_ROOT)}")

        time.sleep(interval_sec)


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Regenerate UML diagrams for docs.")
    parser.add_argument("--watch", action="store_true", help="Watch source files and rerender on changes.")
    parser.add_argument("--interval", type=float, default=1.0, help="Watch polling interval in seconds.")
    args = parser.parse_args()

    if args.watch:
        watch(interval_sec=args.interval)
        return

    total = render_all(verbose=True)
    print(f"done: rendered {total} file(s)")


if __name__ == "__main__":
    main()
