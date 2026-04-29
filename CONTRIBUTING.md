# Contributing

## Quality gate

- **`make verify`** — Canonical strict gate for local and CI: `deps-audit`, lint, types, OpenAPI checks, contract tests, tests, **`make docs-check`**, then **`make docs-a11y-check`**. Run this before push/merge.
- **CI** (GitHub Actions on PR/push) runs the same canonical command: **`make verify`**.
- **CD** (same workflow): on push to **`main`** / **`master`** or a **`v*`** tag, after CI passes, **`publish-image`** pushes the API image to **GitHub Container Registry** (`ghcr.io/<owner>/<repo>`). No extra repo secrets are required; use **Packages** if the image should be public for anonymous pulls.

## Dead code and unused imports

- **Ruff** (via **`make lint-check`** / pre-commit): unused imports (**F401**) and bad **`noqa`** markers (**RUF100**). Fix with **`make lint-fix`**.
- **Vulture** (optional): **`make dead-code-check`** scans for unused code using **`[tool.vulture]`** in `pyproject.toml`. It is **not** part of `verify` because it can report false positives for dynamic code. Review each finding; remove code only when tests or clear evidence support it. A **weekly** GitHub Actions job also runs this scan (see [ADR 0014](docs/adr/0014-dead-code-analysis-and-repository-hygiene.html)).

## Documentation

- Documentation matters a lot in this project. Workflow overview: [docs-pipeline.html](docs/developer/0008-docs-pipeline.html). Why docs live in git: [ADR 0001](docs/adr/0001-docs-as-code.html).
- **GitHub Pages** (branch → `/docs`): the `docs/` folder is the **site root**, so URLs look like `https://<user>.github.io/<repo>/<file>.html`.
- After you change routes, Makefile help, env templates, PlantUML, or HTML under `docs/`, run **`make docs-fix`** and commit so CI stays green.
- **`docs-check`** fails if the docs pipeline would change any file compared to `HEAD` — your branch must already contain everything `docs-fix` would write.
- Docs-only history: [docs/CHANGELOG.md](docs/CHANGELOG.md). ADR lifecycle and GitHub Issue flow: [ADR 0018](docs/adr/0018-adr-lifecycle-ratification-and-badges.html).

## Container image

- **Optional for daily work** — features use **`make run`** and tests; Docker is for packaging and “like production” runs. See the root **README** (*Container image*) and [0009-docker-image-and-container.html](docs/developer/0009-docker-image-and-container.html) for `docker build` and `docker run` notes.
- For **`qa`** / **`prod`**-style runs, supply API keys and stricter settings via environment variables or your deployment platform’s secret mechanism — see **`env/example`** and **`app/core/config.py`**.
- **`scripts/container_entrypoint.sh`** is the container entrypoint logic (migrate + Uvicorn, no `--reload`). The image does not run **`make`**; there is no `.venv` inside the container.

## OpenAPI

- When you change the API on purpose: update the baseline with **`make openapi-accept-changes`** after review, then commit `docs/openapi/openapi-baseline.json` (and code) so **`make openapi-check`** and **`make contract-test`** pass.

## Branches and repository workflow

- Branch names (`feature/…`, `fix/…`, `docs/…`), `main`, tags `v*.*.*`, hotfixes: [ADR 0017](docs/adr/0017-branch-naming-and-repository-workflow.html).
- PR body automation:
  - Keep a local root file `PR_BODY.md` (gitignored). Template source is `.github/PULL_REQUEST_TEMPLATE.md`.
  - On `pre-commit` (non-`main` / non-`master` branches), hook `scripts/check_pr_body.sh` requires `PR_BODY.md` to exist, be non-empty, and have exactly one selected change type (`delivery` / `docs-only` / `mixed`).
  - The same hook also blocks common template placeholders (`What changed and why?`, ``...``) so a raw template is not committed by mistake.
  - On `pre-push`, hook `scripts/sync_pr_body.sh` attempts to update/create branch PR body from `PR_BODY.md` using GitHub CLI (`gh`) but does not block push on `gh` lookup issues.
  - First-time setup:
    - Install GitHub CLI (`gh`) and verify: `gh --version` (for macOS/Homebrew: `brew install gh`).
    - Authenticate: `gh auth login`.
    - Install hooks: `pre-commit install --hook-type pre-commit --hook-type pre-push`.
  - If `gh` is missing, `pre-push` prints guidance and skips sync; install and authenticate `gh`.
  - First push on a brand-new branch may happen before GitHub can resolve the PR head ref; in that case push once more and the hook will create/update PR body on the next push.
  - Manual commands (recommended for deterministic workflow): use `bash scripts/sync_pr_body.sh` and `bash scripts/pr_open.sh`.
  - Repo auto-detection for PR helpers: branch upstream remote (`@{upstream}`) → `origin` → `fork`; optional override: `PR_REPO=<owner/repo>`.
  - Temporary bypass for auto-sync on push: `SKIP_PR_SYNC=1 git push`.

## Architecture decisions (ADRs)

- **Starting work:** open an Issue from [`.github/ISSUE_TEMPLATE/adr_discussion.md`](.github/ISSUE_TEMPLATE/adr_discussion.md) with a title starting with **`[ADR]`** (see [ADR 0018](docs/adr/0018-adr-lifecycle-ratification-and-badges.html)). That Issue is the discussion record; labels are optional.
- **Publishing:** copy [ADR 0000](docs/adr/0000-template.html), pick the next number, add a row to [docs/adr/README.html](docs/adr/README.html), set `data-adr-weight` on `<main>`, and fill **Ratification** (Issue + merge PR + date) when you merge.
- Add a bullet under `[Unreleased]` in [docs/CHANGELOG.md](docs/CHANGELOG.md) when the change is visible to documentation readers.

## Changelog

- If your change affects users (anything in `app/`, `docs/openapi/`, or the main `README.md`), add an entry under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md) in the same PR.
- Add a new `[x.y.z]` section only when you ship a release.
- Do not add several version sections for the same unreleased work, and do not update the changelog more than once per day.
- For small or internal-only changes, you can skip the changelog by putting **`[skip changelog]`** or **`skip-changelog`** in the PR title or commit message. Details: [ADR 0013](docs/adr/0013-changelog-and-release-notes.html).
- **LLM draft (optional):** run `python scripts/changelog_draft.py` to write `changelog-llm-draft.md` (gitignored), then copy bullets into `CHANGELOG.md` under `[Unreleased]`. Offline preview: `python scripts/changelog_draft.py --print-log`. More: [ADR 0013](docs/adr/0013-changelog-and-release-notes.html#llm-draft-workflow).

## Further reading
