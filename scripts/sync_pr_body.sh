#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$branch" == "HEAD" || "$branch" == "main" || "$branch" == "master" ]]; then
  exit 0
fi

pr_body_file="PR_BODY.md"
if [[ ! -s "$pr_body_file" ]]; then
  echo "PR sync: $pr_body_file is missing or empty."
  echo "Run commit first; check_pr_body.sh will create a template when needed."
  exit 0
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "PR sync: GitHub CLI (gh) is not installed."
  echo "Install gh (brew install gh) and run 'gh auth login'."
  exit 0
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "PR sync: gh is not authenticated."
  echo "Run: gh auth login"
  exit 0
fi

if [[ "${SKIP_PR_SYNC:-0}" == "1" ]]; then
  echo "PR sync: skipped (SKIP_PR_SYNC=1)."
  exit 0
fi

detect_repo() {
  if [[ -n "${PR_REPO:-}" ]]; then
    printf "%s" "$PR_REPO"
    return 0
  fi

  local remote_url upstream_ref upstream_remote
  upstream_ref="$(git rev-parse --abbrev-ref --symbolic-full-name "@{upstream}" 2>/dev/null || true)"
  upstream_remote="${upstream_ref%%/*}"

  if [[ -n "$upstream_remote" && "$upstream_remote" != "$upstream_ref" ]]; then
    remote_url="$(git remote get-url "$upstream_remote" 2>/dev/null || true)"
  else
    remote_url="$(git remote get-url origin 2>/dev/null || true)"
    if [[ -z "$remote_url" ]]; then
      remote_url="$(git remote get-url fork 2>/dev/null || true)"
    fi
  fi

  if [[ -n "$remote_url" ]]; then
    # Works for both:
    # - https://github.com/owner/repo.git
    # - git@github.com:owner/repo.git
    local slug
    slug="$(printf '%s' "$remote_url" | sed -E 's#^.*github\.com[:/]([^/]+/[^/.]+)(\.git)?$#\1#')"
    if [[ -n "$slug" && "$slug" != "$remote_url" ]]; then
      printf "%s" "$slug"
      return 0
    fi
  fi

  # Fallback to gh repo context when remote parsing fails.
  gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null || true
}

repo_slug="$(detect_repo || true)"
if [[ -z "${repo_slug:-}" ]]; then
  echo "PR sync: unable to resolve GitHub repo from origin remote."
  echo "PR sync: run manually with --repo <owner/repo> if needed."
  exit 0
fi

default_base="$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || true)"
if [[ -z "${default_base:-}" ]]; then
  default_base="main"
fi

if git rev-parse --verify "origin/$default_base" >/dev/null 2>&1; then
  commits_ahead="$(git rev-list --count "origin/$default_base..HEAD" 2>/dev/null || echo 0)"
  if [[ "${commits_ahead:-0}" -eq 0 ]]; then
    echo "PR sync: no commits ahead of origin/$default_base; skipping PR sync."
    exit 0
  fi
fi

pr_number="$(
  gh pr list \
    --repo "$repo_slug" \
    --state open \
    --head "$branch" \
    --json number \
    --jq '.[0].number' 2>/dev/null || true
)"
if [[ -n "$pr_number" ]]; then
  gh pr edit "$pr_number" --repo "$repo_slug" --body-file "$pr_body_file" >/dev/null
  echo "PR sync: updated PR #$pr_number body from $pr_body_file."
  exit 0
fi

title="$(git log -1 --pretty=%s)"
if [[ -z "$title" ]]; then
  title="$branch"
fi

gh pr create \
  --repo "$repo_slug" \
  --base "$default_base" \
  --head "$branch" \
  --title "$title" \
  --body-file "$pr_body_file" >/tmp/pr_sync_create.out 2>/tmp/pr_sync_create.err || {
    err="$(cat /tmp/pr_sync_create.err 2>/dev/null || true)"
    if echo "$err" | grep -Eq "Head sha can't be blank|Head ref must be a branch|No commits between"; then
      echo "PR sync: branch is likely not available on remote yet (first push)."
      echo "PR sync: push succeeded; run 'git push' once more to auto-create/update PR body."
      exit 0
    fi
    echo "PR sync: gh could not create/update PR; leaving push unblocked."
    if [[ -n "$err" ]]; then
      echo "$err"
    fi
    exit 0
  }

echo "PR sync: created PR for branch $branch in $repo_slug with body from $pr_body_file."
