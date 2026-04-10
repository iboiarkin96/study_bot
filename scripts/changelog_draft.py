#!/usr/bin/env python3
"""Draft Keep a Changelog bullets from git history (optional OpenAI-compatible API).

Assistive only: prints markdown to stdout; humans merge into CHANGELOG.md.
Use ``-o FILE`` to save the same text to a file; do not append raw stdout to
CHANGELOG.md (structure must stay under ``###`` headings you already have).
See docs/adr/0013-changelog-and-release-notes.html.

Uses ``scripts/llm_client.py`` for the API call; see ``env/example``.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from llm_client import chat_completion, default_model, resolve_config


def _git(*args: str) -> str:
    out = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout


def _commit_count(since: str, head: str) -> int:
    raw = _git("rev-list", "--count", f"{since}..{head}").strip()
    return int(raw or 0)


def _working_tree_dirty() -> bool:
    out = subprocess.run(
        ["git", "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return bool(out.strip())


def _build_prompt(
    since: str,
    head: str,
    *,
    include_working_tree: bool = False,
) -> str:
    """Single user message: some OpenAI-compatible routers (e.g. openrouter/free) ignore ``system``."""
    log = _git("log", f"{since}..{head}", "--oneline", "--no-decorate")
    stat = _git("diff", "--stat", since, head)
    tail = ""
    if include_working_tree:
        staged = _git("diff", "--cached", "--stat")
        unstaged = _git("diff", "--stat")
        tail = (
            "\n--- Working tree: staged (git diff --cached --stat) ---\n\n"
            f"{staged or '(none)'}\n\n"
            "--- Working tree: unstaged (git diff --stat) ---\n\n"
            f"{unstaged or '(none)'}\n"
        )
    return (
        "You help maintain a Keep a Changelog style entry under [Unreleased]. "
        "Reply with markdown bullet lists only (### Added / Changed / Fixed as needed). "
        "Be concise; describe user-visible or API-relevant changes; skip pure churn.\n\n"
        "Use only the git data below. If there are no commits in the first section and no "
        "working-tree sections (or they are empty), reply exactly with a single line: "
        "_No changes in this range._\n\n"
        f"--- Git log ({since}..{head}) ---\n\n{log}\n\n"
        f"--- Diff stat ({since}..{head}) ---\n\n{stat}\n"
        f"{tail}"
    )


def main() -> int:
    api_key, base_url, _ = resolve_config()
    default_m = default_model(base_url)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since",
        default="main",
        metavar="REF",
        help="Start ref for git log / diff (default: main)",
    )
    parser.add_argument(
        "--head",
        default="HEAD",
        metavar="REF",
        help="End ref (default: HEAD)",
    )
    parser.add_argument(
        "--model",
        default=default_m,
        help=f"Model id (default: env OPENAI_MODEL or provider default, here {default_m!r})",
    )
    parser.add_argument(
        "--print-log",
        action="store_true",
        help="Print git log/stat only (no API call)",
    )
    parser.add_argument(
        "--include-working-tree",
        action="store_true",
        help="Include staged/unstaged diff --stat (for drafts before you commit)",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Write the draft (or --print-log prompt) to FILE as UTF-8, in addition to stdout",
    )
    args = parser.parse_args()
    out_path = Path(args.output).expanduser() if args.output else None

    user = _build_prompt(
        args.since,
        args.head,
        include_working_tree=args.include_working_tree,
    )
    if args.print_log:
        print(user)
        if out_path is not None:
            out_path.write_text(user + ("\n" if not user.endswith("\n") else ""), encoding="utf-8")
        return 0

    if not api_key:
        print(
            "Set OPENROUTER_API_KEY or OPENAI_API_KEY for LLM draft, "
            "or use --print-log to see git input only.",
            file=sys.stderr,
        )
        return 1

    count = _commit_count(args.since, args.head)
    dirty = _working_tree_dirty()
    # Only committed history counts unless --include-working-tree adds diff stat for local edits.
    if count == 0 and not (args.include_working_tree and dirty):
        msg = "_No changes in this range._"
        print(msg)
        if out_path is not None:
            out_path.write_text(msg + "\n", encoding="utf-8")
        if dirty and not args.include_working_tree:
            print(
                "changelog_draft: no commits on head that are not already in "
                f"{args.since!r}; `git add` does not create commits. "
                "Commit first, or run with --include-working-tree to use staged/unstaged diffs.",
                file=sys.stderr,
            )
        return 0

    try:
        text = chat_completion(user=user, model=args.model)
    except Exception as e:
        print(f"changelog_draft: {e}", file=sys.stderr)
        return 1

    print(text)
    if out_path is not None:
        out_path.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
