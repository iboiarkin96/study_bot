"""Ensure docs HTML pages declare maintainers on the ``<body>`` tag.

This script auto-fixes missing ``data-maintainer-ids`` for docs pages so the
"Edited by" block can always render in the docs UI.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = ROOT / "docs"
DEFAULT_MAINTAINER_ID = "16fc8b78537109162984a2fdbef6e142"
BODY_TAG_RE = re.compile(r"(?is)<body\b([^>]*)>")
MAINTAINERS_ATTR_RE = re.compile(r'data-maintainer-ids\s*=\s*"([^"]*)"')


def iter_docs_pages(candidates: list[str] | None = None) -> list[Path]:
    """Return docs HTML pages eligible for maintainer injection.

    Args:
        candidates: Optional file list (e.g. from pre-commit). If omitted,
            scans all ``docs/**/*.html`` files.

    Returns:
        Sorted list of files under ``docs/`` excluding ``docs/api`` and
        ``docs/assets``.
    """
    if candidates:
        raw_paths = sorted({Path(item).resolve() for item in candidates})
    else:
        raw_paths = sorted(DOCS_ROOT.glob("**/*.html"))

    out: list[Path] = []
    for path in raw_paths:
        if not path.is_file() or path.suffix.lower() != ".html":
            continue
        if DOCS_ROOT not in path.parents:
            continue
        rel = path.relative_to(DOCS_ROOT)
        if rel.parts and rel.parts[0] in {"api", "assets"}:
            continue
        out.append(path)
    return out


def body_has_maintainers(text: str) -> bool:
    """Check whether ``<body>`` has non-empty ``data-maintainer-ids``.

    Args:
        text: Full HTML source.

    Returns:
        ``True`` when the body tag contains a non-empty maintainer ids
        attribute, otherwise ``False``.
    """
    match = BODY_TAG_RE.search(text)
    if not match:
        return False
    attrs = match.group(1)
    m = MAINTAINERS_ATTR_RE.search(attrs)
    return bool(m and m.group(1).strip())


def inject_default_maintainer(text: str) -> str:
    """Inject default maintainer ids into the first ``<body>`` tag.

    Args:
        text: Full HTML source.

    Returns:
        Updated HTML when injection is needed, otherwise original text.
    """
    match = BODY_TAG_RE.search(text)
    if not match:
        return text
    attrs = match.group(1)
    if MAINTAINERS_ATTR_RE.search(attrs):
        return text

    start, end = match.span()
    new_tag = f'<body{attrs} data-maintainer-ids="{DEFAULT_MAINTAINER_ID}">'
    return text[:start] + new_tag + text[end:]


def main() -> None:
    """Run maintainer ids checks/fixes for docs HTML pages."""
    parser = argparse.ArgumentParser(
        description="Ensure docs HTML pages include data-maintainer-ids on <body>."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only validate files and fail if any page misses data-maintainer-ids.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Optional file paths to process (defaults to all docs HTML files).",
    )
    args = parser.parse_args()

    failures: list[Path] = []
    updated = 0
    for path in iter_docs_pages(args.files):
        original = path.read_text(encoding="utf-8")
        if body_has_maintainers(original):
            continue

        if args.check:
            failures.append(path)
            continue

        fixed = inject_default_maintainer(original)
        if fixed != original:
            path.write_text(fixed, encoding="utf-8")
            updated += 1

    if args.check and failures:
        print("Docs maintainer check failed (missing body data-maintainer-ids):")
        for path in failures:
            print(f" - {path.relative_to(ROOT)}")
        raise SystemExit(1)

    if args.check:
        print("Docs maintainer check passed")
    else:
        print(f"Docs maintainer fix completed: {updated} updated")


if __name__ == "__main__":
    main()
