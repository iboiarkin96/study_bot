# Contributing

## Quality gate

- **`make verify`** — Local check: lint, types, OpenAPI, contract tests, tests, **`make docs-fix`**, then **`make docs-a11y-check`**.
- **`make verify-ci`** — Runs **`make deps-audit`** first, then the same steps as **`make verify`**, but uses **`make docs-check`** instead of `docs-fix`, and includes **`make docs-a11y-check`**. **Run this before you push** (or before you merge).
- **CI** (GitHub Actions on PR/push) runs **`make deps-audit`** then **`make verify`** (including docs a11y). The runner still uses **`docs-fix`**, not `docs-check`, so small differences from a fresh `docs-fix` do not fail the job.
- **CD** (same workflow): on push to **`main`** / **`master`** or a **`v*`** tag, after CI passes, **`publish-image`** pushes the API image to **GitHub Container Registry** (`ghcr.io/<owner>/<repo>`). No extra repo secrets are required; use **Packages** if the image should be public for anonymous pulls.

## Dead code and unused imports

- **Ruff** (via **`make lint-check`** / pre-commit): unused imports (**F401**) and bad **`noqa`** markers (**RUF100**). Fix with **`make lint-fix`**.
- **Vulture** (optional): **`make dead-code-check`** scans for unused code using **`[tool.vulture]`** in `pyproject.toml`. It is **not** part of `verify-ci` because it can report false positives for dynamic code. Review each finding; remove code only when tests or clear evidence support it. A **weekly** GitHub Actions job also runs this scan (see [ADR 0014](docs/adr/0014-dead-code-analysis-and-repository-hygiene.html)).

## Documentation

- Documentation matters a lot in this project. Workflow overview: [docs-pipeline.html](docs/developer/0008-docs-pipeline.html). Why docs live in git: [ADR 0001](docs/adr/0001-docs-as-code.html).
- **GitHub Pages** (branch → `/docs`): the `docs/` folder is the **site root**, so URLs look like `https://<user>.github.io/<repo>/<file>.html`.
- After you change routes, Makefile help, env templates, PlantUML, or HTML under `docs/`, run **`make docs-fix`** and commit so CI stays green.
- **`docs-check`** fails if the docs pipeline would change any file compared to `HEAD` — your branch must already contain everything `docs-fix` would write.
- Docs-only history: [docs/CHANGELOG.md](docs/CHANGELOG.md). ADR lifecycle and GitHub Issue flow: [ADR 0018](docs/adr/0018-adr-lifecycle-ratification-and-badges.html).

## Kubernetes local manifests

- **Optional for daily work** — features use **`make run`** and tests; Docker/Kubernetes are for packaging and “like production” runs. See the root **README** (*Container image & local Kubernetes*) and [0009-docker-and-kubernetes-local.html](docs/developer/0009-docker-and-kubernetes-local.html) for the usual dev loop vs a short **deploy** outline (registry → rollout).
- Edit **`k8s/app.env`** for non-secret pod variables; run **`make k8s-render-configmap`** (or **`make docs-fix`**) so **`k8s/configmap.yaml`** stays in sync — it is generated, not edited by hand.
- API keys for **`qa`** / **`prod`**-style runs belong in a Kubernetes **Secret**; see **`k8s/secret.example.yaml`**.
- **`make container-start`** runs **`scripts/container_entrypoint.sh`** (migrate + Uvicorn, no `--reload`) — same as the Docker image. The image does not run **`make`**; there is no `.venv` inside the container.

## OpenAPI

- When you change the API on purpose: update the baseline with **`make openapi-accept-changes`** after review, then commit `docs/openapi/openapi-baseline.json` (and code) so **`make openapi-check`** and **`make contract-test`** pass.

## Branches and repository workflow

- Branch names (`feature/…`, `fix/…`, `docs/…`), `main`, tags `v*.*.*`, hotfixes: [ADR 0017](docs/adr/0017-branch-naming-and-repository-workflow.html).

## Architecture decisions (ADRs)

- **Starting work:** open an Issue from [`.github/ISSUE_TEMPLATE/adr_discussion.md`](.github/ISSUE_TEMPLATE/adr_discussion.md) with a title starting with **`[ADR]`** (see [ADR 0018](docs/adr/0018-adr-lifecycle-ratification-and-badges.html)). That Issue is the discussion record; labels are optional.
- **Publishing:** copy [ADR 0000](docs/adr/0000-template.html), pick the next number, add a row to [docs/adr/README.html](docs/adr/README.html), set `data-adr-weight` on `<main>`, and fill **Ratification** (Issue + merge PR + date) when you merge.
- Add a bullet under `[Unreleased]` in [docs/CHANGELOG.md](docs/CHANGELOG.md) when the change is visible to documentation readers.

## Changelog

- If your change affects users (anything in `app/`, `docs/openapi/`, or the main `README.md`), add an entry under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md) in the same PR.
- Add a new `[x.y.z]` section only when you ship a release.
- Do not add several version sections for the same unreleased work, and do not update the changelog more than once per day.
- For small or internal-only changes, you can skip the changelog by putting **`[skip changelog]`** or **`skip-changelog`** in the PR title or commit message. Details: [ADR 0013](docs/adr/0013-changelog-and-release-notes.html).
- **LLM draft (optional):** `make changelog-draft` writes `changelog-llm-draft.md` (gitignored); copy bullets into `CHANGELOG.md` under `[Unreleased]`. `make llm-ping` checks the API key. Override branch: `make changelog-draft CHANGELOG_HEAD=feature/foo`. Commits only: `make changelog-draft CHANGELOG_DRAFT_FLAGS=`. Offline preview: `python scripts/changelog_draft.py --print-log`. More: [ADR 0013](docs/adr/0013-changelog-and-release-notes.html#llm-draft-workflow).

## Further reading
