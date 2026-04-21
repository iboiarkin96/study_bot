#!/usr/bin/env python3
"""Draft Keep a Changelog bullets from git history (optional OpenAI-compatible API).

Feeds the model **commit subjects and bodies**, **name-status paths**, and diff stat (labeled
as scope-only) so output reflects *what changed*, not only insertion counts.

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


def _git_log_with_messages(since: str, head: str) -> str:
    """Commit history with subject and body (not just oneline)."""
    return _git(
        "log",
        f"{since}..{head}",
        "--reverse",
        "--no-decorate",
        "--pretty=format:%h %s%n%b%n---",
    )


def _git_name_status(since: str, head: str) -> str:
    """Paths changed between refs (M/A/D and file path)."""
    return _git("diff", "--name-status", since, head)


CHANGELOG_SYSTEM_PROMPT = (
    "You draft Keep a Changelog [Unreleased] sections. Output ONLY markdown: "
    "use ### Added, ### Changed, ### Fixed, ### Removed, or ### Security as needed, "
    "each followed by bullet lines starting with '- '.\n\n"
    "Critical rules:\n"
    "- Do NOT summarize using diff statistics only (no answers like 'N files changed' or "
    "'X insertions, Y deletions' as the main content).\n"
    "- Derive meaning from commit subjects and bodies, and from which paths changed "
    "(e.g. docs/, app/, .github/).\n"
    "- Each bullet should describe an outcome: feature, fix, doc, infra, or API behavior — "
    "not raw git metrics.\n"
    "- Merge related commits into one bullet when it reads better.\n"
    "- If commit messages are vague, infer from file paths and still write concrete bullets "
    "(e.g. 'Document container image workflow in developer guides').\n"
)


def _build_prompt(
    since: str,
    head: str,
    *,
    include_working_tree: bool = False,
) -> str:
    """Build user message: rich git context so the model can infer themes, not just diff size."""
    log_detail = _git_log_with_messages(since, head)
    names = _git_name_status(since, head)
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
        "Use only the git data below. If there are no commits in the first section and no "
        "non-empty working-tree sections, reply exactly with one line: _No changes in this range._\n\n"
        f"--- Git log with messages ({since}..{head}, chronological) ---\n\n"
        f"{log_detail or '(no commits)'}\n\n"
        f"--- Changed paths (git diff --name-status) ---\n\n"
        f"{names or '(none)'}\n\n"
        "--- Diff stat (for scope only; do not treat as the changelog) ---\n\n"
        f"{stat or '(none)'}\n"
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
        text = chat_completion(
            user=user,
            system=CHANGELOG_SYSTEM_PROMPT,
            model=args.model,
        )
    except Exception as e:
        print(f"changelog_draft: {e}", file=sys.stderr)
        return 1

    print(text)
    if out_path is not None:
        out_path.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
