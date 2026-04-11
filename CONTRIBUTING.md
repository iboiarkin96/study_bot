# Contributing

## Quality gate

- **`make verify`** — Local gate: lint, types, OpenAPI checks, contract tests, tests, then **`make docs-fix`** (applies doc generation and formatting).
- **`make verify-ci`** — Same as verify but runs **`make docs-check`** instead of `docs-fix`. **Run this before you push** (or before you consider a branch ready to merge).
- **CI** (GitHub Actions on PR/push) runs **`make verify`** (ends with **`docs-fix`** on the runner, not `docs-check`), so the pipeline does not fail when the last committed tree differs slightly from a fresh `docs-fix` output.

### Why `make verify-ci` locally is required

- **`make verify`** finishes by **writing** outputs of the docs pipeline (`docs-fix`). After it runs, your disk can differ from **what is already committed**. CI does **not** compare the runner’s tree to your commits for those files—it only checks that the pipeline succeeds on a clean checkout.
- **`docs-check`** (inside **`verify-ci`**) is the check that fails if **any committed file** would still change after `docs-fix` (synced README, rendered UML, formatted HTML, Makefile-derived snippets, and so on). That is what keeps **GitHub Pages** (`docs/` as the site root) and everyone else’s **`git clone`** aligned with the same sources as the code.
- If you only run **`make verify`** and push without **`verify-ci`**, you can pass CI while shipping **stale or missing** generated docs—reviews and readers will see the wrong pages until someone runs `docs-fix` and commits.

## Dead code and unused imports

- **Ruff** (via **`make lint-check`** / pre-commit): enforces unused imports (**F401**) and drops obsolete **`noqa`** markers (**RUF100**). Fix with **`make lint-fix`**.
- **Vulture** (optional): **`make dead-code-check`** runs a heuristic unused-code scan using **`[tool.vulture]`** in `pyproject.toml`. It is **not** part of `verify-ci` because it can false-positive on dynamic registration; triage each finding and only remove code when tests or clear evidence support it. A **weekly** GitHub Actions job also runs this scan (see [ADR 0014](docs/adr/0014-dead-code-analysis-and-repository-hygiene.html)).

## Documentation

- **GitHub Pages** (Deploy from branch → `/docs`): the `docs/` folder is the **site root**, so public URLs are `https://<user>.github.io/<repo>/<file>.html`
- After changing routes, Makefile help, env templates, PlantUML, or narrative HTML under `docs/`, run **`make docs-fix`** and commit the results so CI passes.
- **`docs-check`** fails if the docs pipeline would change any file relative to `HEAD`—your tree must already include everything `docs-fix` would write.
- Human-written overview: [docs/developer/0008-docs-pipeline.html](docs/developer/0008-docs-pipeline.html). ADR for the practice: [docs/adr/0001-docs-as-code.html](docs/adr/0001-docs-as-code.html).
- Documentation-only history (narrative ADRs, runbooks, guides): [docs/CHANGELOG.md](docs/CHANGELOG.md). ADR lifecycle, badges, and Issue-based discussion: [docs/adr/0018-adr-lifecycle-ratification-and-badges.html](docs/adr/0018-adr-lifecycle-ratification-and-badges.html).

## Kubernetes local manifests

- **Optional for daily development** — feature work uses **`make run`** and tests; Docker/Kubernetes are for packaging and remote-like runs. See the root **README** (section *Container image & local Kubernetes*) and [docs/developer/0009-docker-and-kubernetes-local.html](docs/developer/0009-docker-and-kubernetes-local.html) for the usual dev cycle vs a high-level **real deploy** outline (registry → rollout).
- Edit **`k8s/app.env`** for non-secret pod variables; run **`make k8s-render-configmap`** (or **`make docs-fix`**) so **`k8s/configmap.yaml`** stays in sync — it is generated, not hand-edited.
- API keys for **`qa`**/**`prod`**-style runs belong in a Kubernetes **Secret**; see **`k8s/secret.example.yaml`**.
- **`make container-start`** runs the same **`scripts/container_entrypoint.sh`** as the Docker image (migrate + Uvicorn, no `--reload`). The image does not call **`make`** — there is no `.venv` inside the container.

## OpenAPI

- Intentional API contract changes: update the baseline with **`make openapi-accept-changes`** after review, then commit `docs/openapi/openapi-baseline.json` (and related code) so **`make openapi-check`** and **`make contract-test`** stay green.

## Branches and repository workflow

- Conventions for branch names (`feature/…`, `fix/…`, `docs/…`, etc.), `main` as integration branch, tags `v*.*.*`, and hotfixes: [ADR 0017](docs/adr/0017-branch-naming-and-repository-workflow.html).

## Architecture decisions (ADRs)

- New decisions: open a discussion using [`.github/ISSUE_TEMPLATE/adr_discussion.md`](.github/ISSUE_TEMPLATE/adr_discussion.md), then copy [docs/adr/0000-template.html](docs/adr/0000-template.html), use the next number, add a row to [docs/adr/README.html](docs/adr/README.html), and fill Status badges plus Ratification when merging (see [ADR 0018](docs/adr/0018-adr-lifecycle-ratification-and-badges.html)).
- Add a bullet under `[Unreleased]` in [docs/CHANGELOG.md](docs/CHANGELOG.md) when the change is user-visible for documentation readers.

## Changelog

- If your change affects users (anything in `app/`, `docs/openapi/`, or the main `README.md`), add an entry to the `[Unreleased]` section of [CHANGELOG.md](CHANGELOG.md) in the same pull request.
- Only create a new `[x.y.z]` section when you are making a real release.
- Don’t add multiple version sections for the same unreleased changes, and don’t update the changelog more than once for the same batch of work.
- For purely technical or mechanical changes (that do not affect users), you can skip the changelog update by writing `[skip changelog]` or `skip-changelog` in the PR title or commit message. More details in [ADR 0013](docs/adr/0013-changelog-and-release-notes.html).
- **LLM draft (optional):** `make changelog-draft` writes `changelog-llm-draft.md` (gitignored); copy bullets into `CHANGELOG.md` under `[Unreleased]`. `make llm-ping` checks the API key. Override refs: `make changelog-draft CHANGELOG_HEAD=feature/foo`. Commits only (no staged/unstaged stat): `make changelog-draft CHANGELOG_DRAFT_FLAGS=`. Offline prompt preview: `python scripts/changelog_draft.py --print-log`. Details: [ADR 0013 — Local workflow](docs/adr/0013-changelog-and-release-notes.html#llm-draft-workflow).

## Further reading

- Developer guides index: [docs/developer/README.html](docs/developer/README.html)
