#!/usr/bin/env python3
"""Enforce CHANGELOG.md updates when user-facing paths change (CI helper).

See docs/adr/0013-changelog-and-release-notes.html.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

CODE_PREFIXES = ("app/",)
DOCS_PREFIXES = ("docs/openapi/",)
ROOT_TRIGGER_FILES = frozenset({"README.md"})
ROOT_CHANGELOG = "CHANGELOG.md"
DOCS_CHANGELOG = "docs/CHANGELOG.md"
SKIP_SUBSTRINGS = ("[skip changelog]", "skip-changelog")


def _git(*args: str) -> str:
    out = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout


def _is_all_zeros(ref: str) -> bool:
    s = ref.strip().lower()
    return s == "0" * len(s) and len(s) >= 40


def _classify_triggers(paths: list[str]) -> tuple[bool, bool]:
    """Return trigger flags for code-facing and docs-facing changes.

    Args:
        paths: Changed paths in git diff range.

    Returns:
        Tuple ``(needs_root_changelog, needs_docs_changelog)``.
    """
    needs_root = False
    needs_docs = False
    for p in paths:
        p = p.replace("\\", "/").strip()
        if not p:
            continue
        if p in ROOT_TRIGGER_FILES:
            needs_root = True
        if any(p.startswith(prefix) for prefix in CODE_PREFIXES):
            needs_root = True
        if any(p.startswith(prefix) for prefix in DOCS_PREFIXES):
            needs_docs = True
    return needs_root, needs_docs


def _skip_in_text(text: str) -> bool:
    lower = text.lower()
    return any(s in lower for s in SKIP_SUBSTRINGS)


def _changed_files(base: str, head: str) -> list[str]:
    raw = _git("diff", "--name-only", base, head)
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _commit_messages(base: str, head: str) -> str:
    try:
        return _git("log", f"{base}..{head}", "--format=%B%n")
    except subprocess.CalledProcessError:
        return ""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", required=True, help="Git ref (start of range)")
    p.add_argument("--head", required=True, help="Git ref (end of range)")
    p.add_argument(
        "--event",
        choices=("pr", "push"),
        default="pr",
        help="pr: read PR_TITLE from env for skip; push: scan commit messages",
    )
    args = p.parse_args()

    if args.event == "push" and _is_all_zeros(args.base):
        print("changelog_gate: skipping (before ref is all zeros / new branch)")
        return 0

    paths = _changed_files(args.base, args.head)
    needs_root, needs_docs = _classify_triggers(paths)
    if not (needs_root or needs_docs):
        print("changelog_gate: ok (no user-facing paths in range)")
        return 0

    changed_paths = {x.replace("\\", "/") for x in paths}
    has_root_changelog = ROOT_CHANGELOG in changed_paths
    has_docs_changelog = DOCS_CHANGELOG in changed_paths

    missing: list[str] = []
    if needs_root and not has_root_changelog:
        missing.append(ROOT_CHANGELOG)
    if needs_docs and not (has_docs_changelog or has_root_changelog):
        # Allow root changelog as an override for docs/openapi changes.
        missing.append(DOCS_CHANGELOG)

    if not missing:
        print("changelog_gate: ok (required changelog file(s) updated)")
        return 0

    if args.event == "pr":
        title = os.environ.get("PR_TITLE", "")
        if _skip_in_text(title):
            print("changelog_gate: ok (skip token in PR title)")
            return 0
    else:
        if _skip_in_text(_commit_messages(args.base, args.head)):
            print("changelog_gate: ok (skip token in commit message(s))")
            return 0

    print("changelog_gate: missing required changelog update(s):", file=sys.stderr)
    for path in missing:
        print(f"  - {path}", file=sys.stderr)
    print(
        "Rules: app/ and root README.md require CHANGELOG.md; docs/openapi/ "
        f"requires {DOCS_CHANGELOG} (or {ROOT_CHANGELOG}). "
        "You can bypass via [skip changelog] or skip-changelog in PR title "
        "(PR) or commit messages (push).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
