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

## OpenAPI

- Intentional API contract changes: update the baseline with **`make openapi-accept-changes`** after review, then commit `docs/openapi/openapi-baseline.json` (and related code) so **`make openapi-check`** and **`make contract-test`** stay green.

## Architecture decisions (ADRs)

- New decisions: copy [docs/adr/0000-template.html](docs/adr/0000-template.html), use the next number, add a row to [docs/adr/README.html](docs/adr/README.html), and follow the structure.

## Changelog

- User-facing edits under `app/`, `docs/openapi/`, or the root `README.md` should include an update under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md) in the same pull request. Add a new dated `[x.y.z]` section only when you cut a release—do not stack multiple version sections for the same unpublished work, and avoid editing the log twice for one uncommitted batch.
- To skip the changelog requirement for mechanical changes, put `[skip changelog]` or `skip-changelog` in the PR title (or in commit messages on pushes to `main`/`master`). Policy and CI details: [ADR 0013](docs/adr/0013-changelog-and-release-notes.html).
- Optional: run `python scripts/changelog_draft.py --print-log` to inspect git input, or set `OPENAI_API_KEY` (and optionally `OPENAI_BASE_URL`) for a draft printed to stdout—still reviewed by humans before merge.

## Further reading

- Developer guides index: [docs/developer/README.html](docs/developer/README.html)
