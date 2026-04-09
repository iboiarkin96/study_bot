# Contributing

## Quality gate

- **`make verify`** — Local gate: lint, types, OpenAPI checks, contract tests, tests, then **`make docs-fix`** (applies doc generation and formatting).
- **`make verify-ci`** — Same as verify but runs **`make docs-check`** instead of `docs-fix`. Use before pushing; CI runs this on every PR.

## Documentation

- **GitHub Pages** (Deploy from branch → `/docs`): the `docs/` folder is the **site root**, so public URLs are `https://<user>.github.io/<repo>/<file>.html` — **not** `…/<repo>/docs/<file>.html` (that path 404s). Example: `system-analysis.html` → `…/study_bot/system-analysis.html`.
- After changing routes, Makefile help, env templates, PlantUML, or narrative HTML under `docs/`, run **`make docs-fix`** and commit the results so CI passes.
- **`docs-check`** fails if the docs pipeline would change any file relative to `HEAD`—your tree must already include everything `docs-fix` would write.
- Human-written overview: [docs/developer/0008-docs-pipeline.html](docs/developer/0008-docs-pipeline.html). ADR for the practice: [docs/adr/0001-docs-as-code.html](docs/adr/0001-docs-as-code.html).

## OpenAPI

- Intentional API contract changes: update the baseline with **`make openapi-accept-changes`** after review, then commit `docs/openapi/openapi-baseline.json` (and related code) so **`make openapi-check`** and **`make contract-test`** stay green.

## Architecture decisions (ADRs)

- New decisions: copy [docs/adr/0000-template.html](docs/adr/0000-template.html), use the next number, add a row to [docs/adr/README.html](docs/adr/README.html), and follow the structure in [ADR 0001](docs/adr/0001-docs-as-code.html).

## Further reading

- Developer guides index: [docs/developer/README.html](docs/developer/README.html)
