"""Regenerate rendered UML diagrams for project documentation.

Usage:
  python scripts/regenerate_docs.py
  python scripts/regenerate_docs.py --check
  python scripts/regenerate_docs.py --watch
  python scripts/regenerate_docs.py --bootstrap-manifest   # offline: fill input-hashes.json
  python scripts/regenerate_docs.py --force                 # ignore cache, re-render all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UML_SRC_DIR = PROJECT_ROOT / "docs" / "uml"
UML_OUT_DIR = PROJECT_ROOT / "docs" / "uml" / "rendered"
UML_STYLE_FILE = UML_SRC_DIR / "include" / "style.puml"
# Committed fingerprint store: skip Kroki when merged PlantUML + PNG bytes match last run.
UML_MANIFEST_PATH = UML_SRC_DIR / "input-hashes.json"
MANIFEST_VERSION = 1
# PNG quality is controlled mainly by skinparam dpi in docs/uml/include/style.puml (sent in the diagram body).
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


def _merge_style(source_path: Path) -> str:
    """Return PlantUML text sent to Kroki: optional shared skin after ``@startuml``.

    Kroki receives a single file; ``docs/uml/include/style.puml`` is injected so sources
    stay DRY. Use ``!NO_STYLE`` on the line after ``@startuml`` to skip injection.

    Args:
        source_path: Path to a diagram ``*.puml`` (not ``include/*.puml``).

    Returns:
        Full document body as UTF-8 text.
    """
    raw = source_path.read_text(encoding="utf-8")
    lines = raw.splitlines(keepends=True)
    if not lines:
        return raw
    if lines[0].strip().lower() != "@startuml":
        return raw
    if len(lines) > 1 and lines[1].strip() == "!NO_STYLE":
        return "".join([lines[0]] + lines[2:])
    if not UML_STYLE_FILE.is_file():
        return raw
    style = UML_STYLE_FILE.read_text(encoding="utf-8")
    if style and not style.endswith("\n"):
        style += "\n"
    return lines[0] + style + "".join(lines[1:])


def _source_files() -> list[Path]:
    """Collect every diagram ``*.puml`` under ``docs/uml``.

    Skips ``rendered/`` outputs and ``include/`` fragments (e.g. shared ``style.puml``).

    Returns:
        Sorted list of source paths.
    """
    files = sorted(UML_SRC_DIR.rglob("*.puml"))
    result: list[Path] = []
    for f in files:
        if "rendered" in f.parts:
            continue
        rel = f.relative_to(UML_SRC_DIR)
        if rel.parts and rel.parts[0] == "include":
            continue
        result.append(f)
    return result


def _output_for(source_path: Path) -> Path:
    """Map a ``.puml`` path to the PNG path under ``docs/uml/rendered``.

    Args:
        source_path: Absolute path to a PlantUML file.

    Returns:
        Destination PNG path (sequence diagrams keep stem-only names).
    """
    rel = source_path.relative_to(UML_SRC_DIR)
    # Keep legacy names for sequence diagrams to avoid breaking docs/internal/system-design.html.
    if rel.parts and rel.parts[0] == "sequences":
        safe_name = source_path.stem + ".png"
    else:
        # Keep filenames stable and unique across non-sequence subdirectories.
        safe_name = "__".join(rel.with_suffix("").parts) + ".png"
    return UML_OUT_DIR / safe_name


def _rel_key(source_path: Path) -> str:
    """Stable posix path of ``source_path`` relative to ``docs/uml``."""
    return source_path.relative_to(UML_SRC_DIR).as_posix()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _input_sha256(source_path: Path) -> str:
    """SHA-256 of the UTF-8 merged document sent to Kroki (includes injected style)."""
    merged = _merge_style(source_path)
    return _sha256_bytes(merged.encode("utf-8"))


def _load_manifest_diagrams() -> dict[str, dict[str, str]]:
    """Load ``diagrams`` map from :data:`UML_MANIFEST_PATH`; missing or bad file → empty."""
    if not UML_MANIFEST_PATH.is_file():
        return {}
    try:
        raw = json.loads(UML_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if raw.get("version") != MANIFEST_VERSION:
        return {}
    diagrams = raw.get("diagrams")
    if not isinstance(diagrams, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for key, val in diagrams.items():
        if not isinstance(key, str) or not isinstance(val, dict):
            continue
        inp = val.get("input_sha256")
        outp = val.get("output_sha256")
        if isinstance(inp, str) and isinstance(outp, str) and len(inp) == 64 and len(outp) == 64:
            out[key] = {"input_sha256": inp, "output_sha256": outp}
    return out


def _persist_render_in_manifest(source_path: Path, output_path: Path) -> None:
    """Update or insert one diagram entry and prune orphans (used by watch mode)."""
    diagrams = _load_manifest_diagrams()
    key = _rel_key(source_path)
    diagrams[key] = {
        "input_sha256": _input_sha256(source_path),
        "output_sha256": _sha256_bytes(output_path.read_bytes()),
    }
    keep = {_rel_key(s) for s in _source_files()}
    diagrams = {k: v for k, v in diagrams.items() if k in keep}
    _save_manifest_diagrams(diagrams)


def _save_manifest_diagrams(diagrams: dict[str, dict[str, str]]) -> None:
    """Atomically write manifest (sorted keys for stable diffs)."""
    payload: dict[str, Any] = {
        "version": MANIFEST_VERSION,
        "diagrams": dict(sorted(diagrams.items())),
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    UML_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=".input-hashes-",
        suffix=".json",
        dir=str(UML_MANIFEST_PATH.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        Path(tmp).replace(UML_MANIFEST_PATH)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def render_one(source_path: Path, output_path: Path) -> None:
    """Render one PlantUML file to PNG via POST to :data:`KROKI_URL` using ``curl``.

    Injects :data:`UML_STYLE_FILE` after the opening ``@startuml`` line when present so
    Kroki receives one self-contained document (``!include`` is not resolved server-side).

    Args:
        source_path: Input ``.puml`` file.
        output_path: Target ``.png`` path (parent dirs created).

    Raises:
        subprocess.CalledProcessError: If ``curl`` exits non-zero.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged = _merge_style(source_path)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".puml",
        delete=False,
    ) as tmp:
        tmp.write(merged)
        tmp_path = tmp.name
    try:
        cmd = [
            "curl",
            "-k",
            "-sS",
            "-f",
            "-X",
            "POST",
            "-H",
            "Content-Type: text/plain",
            "--data-binary",
            f"@{tmp_path}",
            KROKI_URL,
            "-o",
            str(output_path),
        ]
        subprocess.run(cmd, check=True)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def render_all(verbose: bool = True, *, force: bool = False) -> tuple[int, int]:
    """Render PlantUML sources to PNGs, skipping Kroki when manifest and bytes match.

    Uses :data:`UML_MANIFEST_PATH` (input + output SHA-256 per diagram). Orphan manifest
    keys are removed after a successful run.

    Args:
        verbose: When True, print one line per file via :func:`_ok`.
        force: When True, ignore the manifest and re-render every diagram.

    Returns:
        ``(rendered, skipped)`` — counts of Kroki renders vs cache hits.
    """
    files = _source_files()
    diagrams: dict[str, dict[str, str]] = {} if force else _load_manifest_diagrams()
    rendered = 0
    skipped = 0
    for src in files:
        out = _output_for(src)
        key = _rel_key(src)
        in_h = _input_sha256(src)
        if not force and out.is_file():
            entry = diagrams.get(key)
            out_h = _sha256_bytes(out.read_bytes())
            if entry and entry["input_sha256"] == in_h and entry["output_sha256"] == out_h:
                skipped += 1
                if verbose:
                    _ok(f"Skipped (unchanged) {out.relative_to(PROJECT_ROOT)}")
                continue
        render_one(src, out)
        out_h = _sha256_bytes(out.read_bytes())
        diagrams[key] = {"input_sha256": in_h, "output_sha256": out_h}
        rendered += 1
        if verbose:
            _ok(f"Rendered {out.relative_to(PROJECT_ROOT)}")
    keep = {_rel_key(s) for s in files}
    diagrams = {k: v for k, v in diagrams.items() if k in keep}
    _save_manifest_diagrams(diagrams)
    return rendered, skipped


def bootstrap_manifest(verbose: bool = True) -> int:
    """Fill ``input-hashes.json`` from current sources and PNGs without calling Kroki.

    Use when introducing the fingerprint file or offline; assumes each ``.puml`` already
    matches its ``rendered/*.png``.

    Args:
        verbose: Print one status line per diagram.

    Returns:
        Number of diagrams recorded.

    Raises:
        SystemExit: If any diagram has no PNG on disk.
    """
    diagrams: dict[str, dict[str, str]] = {}
    for src in _source_files():
        out = _output_for(src)
        if not out.is_file():
            print(
                f"✗ Missing PNG for {src.relative_to(PROJECT_ROOT)} — run docs-fix with network first."
            )
            raise SystemExit(1)
        key = _rel_key(src)
        in_h = _input_sha256(src)
        out_h = _sha256_bytes(out.read_bytes())
        diagrams[key] = {"input_sha256": in_h, "output_sha256": out_h}
        if verbose:
            _ok(f"Recorded {key}")
    _save_manifest_diagrams(diagrams)
    return len(diagrams)


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
    """Compare each source/output pair; uses manifest + hashes first, then Kroki if needed.

    Args:
        verbose: Print per-file status lines.

    Returns:
        Number of diagrams whose output is missing or differs from a fresh render.
    """
    stale = 0
    files = _source_files()
    diagrams = _load_manifest_diagrams()
    for src in files:
        out = _output_for(src)
        key = _rel_key(src)
        in_h = _input_sha256(src)
        entry = diagrams.get(key)
        if entry and entry["input_sha256"] == in_h and out.is_file():
            out_h = _sha256_bytes(out.read_bytes())
            if out_h == entry["output_sha256"]:
                if verbose:
                    _ok(f"Up to date {out.relative_to(PROJECT_ROOT)}")
                continue
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

    rendered, skipped = render_all(verbose=True)
    _ok(
        f"Initial render done: {rendered + skipped} file(s) ({rendered} rendered, {skipped} from cache)"
    )

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
            _persist_render_in_manifest(src, out)
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-render every diagram (ignore input-hashes.json).",
    )
    parser.add_argument(
        "--bootstrap-manifest",
        action="store_true",
        help="Write input-hashes.json from current .puml/.png only (no Kroki).",
    )
    args = parser.parse_args()

    if args.bootstrap_manifest:
        if args.watch or args.check or args.force:
            print("✗ --bootstrap-manifest cannot be combined with --watch, --check, or --force.")
            raise SystemExit(2)
        _step("Bootstrapping input-hashes.json (no Kroki)…")
        n = bootstrap_manifest(verbose=True)
        _ok(f"Recorded {n} diagram(s) in {UML_MANIFEST_PATH.relative_to(PROJECT_ROOT)}")
        return

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
    rendered, skipped = render_all(verbose=True, force=args.force)
    if skipped:
        _ok(f"Done: {rendered} rendered, {skipped} unchanged (see {UML_MANIFEST_PATH.name})")
    else:
        _ok(f"Done: rendered {rendered} file(s)")


if __name__ == "__main__":
    main()
