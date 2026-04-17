# Contributing

## Quality gate

- **`make verify`** — Local gate: lint, types, OpenAPI checks, contract tests, tests, **`make docs-fix`** (doc generation + formatting), then **`make docs-a11y-check`**.
- **`make verify-ci`** — Runs **`make deps-audit`** first, then the same steps as **`make verify`** but **`make docs-check`** instead of `docs-fix`, and includes **`make docs-a11y-check`**. **Run this before you push** (or before you consider a branch ready to merge).
- **CI** (GitHub Actions on PR/push) runs **`make deps-audit`** then **`make verify`** (including docs a11y baseline checks). It still uses **`docs-fix`** on the runner instead of `docs-check`, so the pipeline does not fail when the last committed tree differs slightly from a fresh `docs-fix` output.
- **CD** (same workflow): on push to **`main`** / **`master`** or a **`v*`** tag, after CI succeeds, the **`publish-image`** job pushes the API container image to **GitHub Container Registry** (`ghcr.io/<owner>/<repo>`). No extra repository secrets are required; use **Packages** settings if the image should be public for pulls without authentication.


## Dead code and unused imports

- **Ruff** (via **`make lint-check`** / pre-commit): enforces unused imports (**F401**) and drops obsolete **`noqa`** markers (**RUF100**). Fix with **`make lint-fix`**.
- **Vulture** (optional): **`make dead-code-check`** runs a heuristic unused-code scan using **`[tool.vulture]`** in `pyproject.toml`. It is **not** part of `verify-ci` because it can false-positive on dynamic registration; triage each finding and only remove code when tests or clear evidence support it. A **weekly** GitHub Actions job also runs this scan (see [ADR 0014](docs/adr/0014-dead-code-analysis-and-repository-hygiene.html)).

## Documentation
- Documentation is highly prioritized in this project. For an overview of the documentation workflow, see: [docs-pipeline.html](docs/developer/0008-docs-pipeline.html). For the rationale behind the docs-as-code approach, refer to the ADR: [ADR 0001](docs/adr/0001-docs-as-code.html).
- **GitHub Pages** (Deploy from branch → `/docs`): the `docs/` folder is the **site root**, so public URLs are `https://<user>.github.io/<repo>/<file>.html`
- After changing routes, Makefile help, env templates, PlantUML, or narrative HTML under `docs/`, run **`make docs-fix`** and commit the results so CI passes.
- **`docs-check`** fails if the docs pipeline would change any file relative to `HEAD`—your tree must already include everything `docs-fix` would write.
- Documentation-only history (narrative ADRs, runbooks, guides): [docs/CHANGELOG.md](docs/CHANGELOG.md). ADR lifecycle, status model, and Issue-based discussion: [ADR 0018](docs/adr/0018-adr-lifecycle-ratification-and-badges.html).

## Kubernetes local manifests

- **Optional for daily development** — feature work uses **`make run`** and tests; Docker/Kubernetes are for packaging and remote-like runs. See the root **README** (section *Container image & local Kubernetes*) and [0009-docker-and-kubernetes-local.html](docs/developer/0009-docker-and-kubernetes-local.html) for the usual dev cycle vs a high-level **real deploy** outline (registry → rollout).
- Edit **`k8s/app.env`** for non-secret pod variables; run **`make k8s-render-configmap`** (or **`make docs-fix`**) so **`k8s/configmap.yaml`** stays in sync — it is generated, not hand-edited.
- API keys for **`qa`**/**`prod`**-style runs belong in a Kubernetes **Secret**; see **`k8s/secret.example.yaml`**.
- **`make container-start`** runs the same **`scripts/container_entrypoint.sh`** as the Docker image (migrate + Uvicorn, no `--reload`). The image does not call **`make`** — there is no `.venv` inside the container.

## OpenAPI

- Intentional API contract changes: update the baseline with **`make openapi-accept-changes`** after review, then commit `docs/openapi/openapi-baseline.json` (and related code) so **`make openapi-check`** and **`make contract-test`** stay green.

## Branches and repository workflow

- Conventions for branch names (`feature/…`, `fix/…`, `docs/…`, etc.), `main` as integration branch, tags `v*.*.*`, and hotfixes: [ADR 0017](docs/adr/0017-branch-naming-and-repository-workflow.html).

## Architecture decisions (ADRs)

- **Marking the work:** open an Issue from [`.github/ISSUE_TEMPLATE/adr_discussion.md`](.github/ISSUE_TEMPLATE/adr_discussion.md) and use a title starting with **`[ADR]`** (see [ADR 0018](docs/adr/0018-adr-lifecycle-ratification-and-badges.html)). That Issue is the discussion record; optional GitHub labels are not required.
- **Publishing:** copy [ADR 0000](docs/adr/0000-template.html), take the next number, add a row to [docs/adr/README.html](docs/adr/README.html), set `data-adr-weight` on `<main>`, and fill **Ratification** (Issue + merge PR + date) when you merge.
- Add a bullet under `[Unreleased]` in [docs/CHANGELOG.md](docs/CHANGELOG.md) when the change is user-visible for documentation readers.

## Changelog

- If your change affects users (anything in `app/`, `docs/openapi/`, or the main `README.md`), add an entry to the `[Unreleased]` section of [CHANGELOG.md](CHANGELOG.md) in the same pull request.
- Only create a new `[x.y.z]` section when you are making a real release.
- Don’t add multiple version sections for the same set of unreleased changes, and don’t update the changelog more than once per day.
- For purely technical or mechanical changes (that do not affect users), you can skip the changelog update by writing `[skip changelog]` or `skip-changelog` in the PR title or commit message. More details in [ADR 0013](docs/adr/0013-changelog-and-release-notes.html).
- **LLM draft (optional):** `make changelog-draft` writes `changelog-llm-draft.md` (gitignored); copy bullets into `CHANGELOG.md` under `[Unreleased]`. `make llm-ping` checks the API key. Override refs: `make changelog-draft CHANGELOG_HEAD=feature/foo`. Commits only (no staged/unstaged stat): `make changelog-draft CHANGELOG_DRAFT_FLAGS=`. Offline prompt preview: `python scripts/changelog_draft.py --print-log`. Details: [ADR 0013](docs/adr/0013-changelog-and-release-notes.html#llm-draft-workflow).


## Further reading
