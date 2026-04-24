#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$branch" == "HEAD" || "$branch" == "main" || "$branch" == "master" ]]; then
  echo "PR open: current branch is $branch; switch to a feature/docs/fix branch first."
  exit 1
fi

detect_repo() {
  if [[ -n "${PR_REPO:-}" ]]; then
    printf "%s" "$PR_REPO"
    return 0
  fi

  local remote_url slug upstream_ref upstream_remote
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
    slug="$(printf '%s' "$remote_url" | sed -E 's#^.*github\.com[:/]([^/]+/[^/.]+)(\.git)?$#\1#')"
    if [[ -n "$slug" && "$slug" != "$remote_url" ]]; then
      printf "%s" "$slug"
      return 0
    fi
  fi

  gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null || true
}

repo_slug="$(detect_repo || true)"
if [[ -z "${repo_slug:-}" ]]; then
  echo "PR open: cannot resolve GitHub repo."
  echo "PR open: set PR_REPO=<owner/repo>, then rerun."
  exit 1
fi

default_base="$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || true)"
if [[ -z "${default_base:-}" ]]; then
  default_base="main"
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
  gh pr view "$pr_number" --repo "$repo_slug" --web
  exit 0
fi

title="$(git log -1 --pretty=%s)"
if [[ -z "$title" ]]; then
  title="$branch"
fi

if [[ -s "PR_BODY.md" ]]; then
  gh pr create \
    --repo "$repo_slug" \
    --base "$default_base" \
    --head "$branch" \
    --title "$title" \
    --body-file "PR_BODY.md" \
    --web
else
  gh pr create \
    --repo "$repo_slug" \
    --base "$default_base" \
    --head "$branch" \
    --fill \
    --web
fi
