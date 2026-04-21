# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Documentation:** internal employee portal (`docs/internal/portal/`), generated portal data in `docs/assets/docs-portal-data.js`, page history sections and validation on hand-written HTML, and related scripts (`collect_docs_portal_data.py`, `ensure_docs_page_history.py`, and helpers). Details: [`docs/CHANGELOG.md`](docs/CHANGELOG.md#2026-04-21).

- Documentation HTML pages now use a shared favicon (`docs/assets/favicon.svg`), including `docs/openapi/openapi-explorer.html`, with generation/backfill scripts keeping favicon links consistent across regenerated docs output.

### Removed

- Sample multi-file deployment manifests, the env-to-manifest render script, and the matching Make targets. Documentation and ADR 0015 now describe the Docker image only; see `docs/developer/0009-docker-image-and-container.html`.

## [1.1.1] — 2026-04-17

### Added

- Client-side docs search implementation package:
  - index builder `scripts/build_docs_search_index.py`,
  - generated artifact `docs/assets/search-index.json`,
  - ranking/runtime UI integration in `docs/assets/docs-nav.js`,
  - ADR `docs/adr/0027-client-side-docs-search-index-and-ranking.html`.


- Docs-search telemetry ingestion and aggregation:
  - store module `app/core/docs_search_telemetry.py`,
  - API schema `app/schemas/telemetry.py`,
  - ingest endpoint `POST /internal/telemetry/docs-search`,
  - metrics endpoint `GET /internal/telemetry/docs-search/metrics`.

- RFC documentation area for implementation-level specs:
  - `docs/rfc/README.html`,
  - `docs/rfc/0001-docs-search-implementation.html`.

- Formal accessibility workflow: `.github/workflows/a11y-formal-checks.yml`.

### Changed

- Internal and top navigation updated to include ADR/RFC entry points and stable links from docs home and internal pages.

- Local docs-search troubleshooting and validation guidance expanded in developer docs (`docs/developer/0007-local-development.html`), including CORS/preflight and SQLite verification steps.

## [1.1.1] — 2026-04-12

### Added

- ADR 0017: branch naming (`feature/`, `fix/`, `docs/`, `chore/`, `refactor/`), `main` as integration branch, release tags `v*.*.*`, and hotfix forward-port guidance.

- ADR 0020: C4 views, PlantUML conventions, shared diagram style (`docs/uml/include/style.puml`), and `docs/uml/README.txt` for authors.

- [ADR 0021](docs/adr/0021-continuous-delivery-github-actions-and-ghcr.html): continuous delivery of the container image (GitHub Actions → GHCR), CI vs CD, scope, and why runtime secrets stay outside the workflow.

- GitHub Actions: **CD** job **`publish-image`** builds the [`Dockerfile`](Dockerfile) and pushes to **GHCR** (`ghcr.io/<owner>/<repo>`) on successful **`quality`** (and **`changelog`** when that job runs) after push to **`main`** / **`master`** or **`v*`** tags. Uses the default **`GITHUB_TOKEN`** (`packages: write`); image tags include **short SHA**, **`latest`** on the default branch, and **semver** labels on version tags.

- **Embedded Swagger UI:** [docs/openapi/openapi-explorer.html](docs/openapi/openapi-explorer.html) loads the committed OpenAPI snapshot (`docs/openapi/openapi-baseline.json`) with **Try it out**; top nav link **Swagger UI**; linked from docs index, developer index, and README.

- **Structured logging and optional local Elasticsearch:** NDJSON (`LOG_FORMAT=json`, or leave unset — application default is **json**), `LOG_SERVICE_NAME`, `X-Request-Id` middleware, `docker-compose.logging.yml` (Elasticsearch, Kibana, Filebeat), `make logging-up` / `logging-down` / `logging-smoke` / `logging-reset` / `logging-es-query`, and [ADR 0023](docs/adr/0023-structured-logging-and-local-elasticsearch.html). `trace_id` / `span_id` are reserved in JSON logs for future OpenTelemetry.

- **X-Request-Id in browsers and Swagger:** `CORS_EXPOSE_HEADERS` (default includes `X-Request-Id`) so cross-origin clients can read the correlation header; OpenAPI documents optional request header and response `X-Request-Id` on every operation for Swagger UI **Try it out**.

- **Logging defaults for correlation:** `LOG_FORMAT` defaults to **json** (NDJSON with top-level `request_id`); `env/dev` sets `LOG_FORMAT` + `CORS_EXPOSE_HEADERS`; Uvicorn runs with **`--no-access-log`** so duplicate `uvicorn.access` lines (without `request_id`) are not written—HTTP traces use `app.main` `request_done` only.

- **Kibana / Elasticsearch:** Documented data view index pattern **`*study-app-logs*`** (not only `study-app-logs-*`) so Discover includes `.ds-study-app-logs-*` backing indices; Filebeat sets **`setup.template.type: legacy`** for classic daily index names on new data.

- **Dependency security (backlog item-4):** `pip-audit` was already pinned and run in CI; **`make verify-ci`** now runs **`make deps-audit`** first so local pre-push matches the **`quality`** job (`deps-audit` then **`make verify`**). Backlog [item-4](docs/backlog/README.html#item-4) marked **Done**; [ADR 0019](docs/adr/0019-python-dependency-security-pip-audit-and-pinning-policy.html) implementation status set to **Done** (`data-adr-weight="7"`).

### Changed

- PlantUML in `docs/uml/`: diagram sources and rendered SVGs updated; shared style via `docs/uml/include/style.puml` ([ADR 0020](docs/adr/0020-c4-plantuml-diagram-style-and-conventions.html)).

- Documentation pipeline and contributor touchpoints: `scripts/regenerate_docs.py`, `scripts/sync_docs.py`, `Makefile`, `CONTRIBUTING.md`, `.github/ISSUE_TEMPLATE/adr_discussion.md`, and synced HTML pages (e.g. engineering practices, system design, backlog, runbooks, developer docs) brought in line with ADR lifecycle and UML generation.

- **OpenAPI (test):** **`docs/openapi/openapi-explorer.html`** — Swagger UI against `openapi-baseline.json` for browsing only (**Try it out** disabled). Browser-side Ajv validation and **`docs/assets/openapi-sandbox.js`** removed. **[ADR 0022](docs/adr/0022-embedded-swagger-ui-openapi-sandbox.html)** marked superseded; validation approach on hold. **`docs/openapi-live.html`** removed (use app **`/docs`** for Try it out). README and indexes updated.

- **CORS (`env/example`):** comment clarifies static `docs/openapi/openapi-explorer.html` does not call the API; origins for `:8765` remain for browser access to the API from the same docs origin (e.g. FastAPI `/docs`).

## [1.1.1] — 2026-04-11

### Added

- ADR 0014: dead-code hygiene (Ruff F401/RUF100, Vulture, `make dead-code-check`, weekly workflow).
- ADR document `docs/adr/0013-changelog-and-release-notes.html` outlining changelog and release‑notes policy.
- New script `scripts/llm_client.py` providing an LLM client interface.
- New script `scripts/llm_ping.py` for health‑checking the LLM service.
- `Dockerfile`, `.dockerignore`, and `scripts/container_entrypoint.sh` for reproducible container builds.
- README and developer guide clarify that Docker is optional for daily development, and outline how real-world deploys typically use a registry and target environment.
- Developer guide for the container image and ADR 0015 (container image).
- Makefile targets `docker-build`, `container-start` (same entrypoint script as Docker).
- ADR 0016 (Google-style Python docstrings, alignment with `make api-docs` / pdoc), developer index entry, and `.cursor/rules/python-docstrings.mdc` for editor guidance; expanded module docstrings across `app/`.

### Changed

- GitHub Actions quality job runs `make verify` (applies `docs-fix` on the runner) instead of `make verify-ci` / `docs-check`, avoiding false failures when generated docs drift from `HEAD`.
- Updated `CONTRIBUTING.md` with new contribution guidelines.
- Minor adjustments to `Makefile` for build and test targets.
- Updated `requirements.txt` to include dependencies required by the new LLM scripts.
- Refactored `scripts/changelog_draft.py` to integrate LLM generation logic and improve draft creation.
- `CHANGELOG.md`, `README.md`, and `CONTRIBUTING.md` updated for container workflows and discovery of new docs.
- `docs/adr/README.html`, `docs/developer/README.html`, and `docs/internal/developers.html` link to ADR 0015 and the Docker image developer guide.
- `env/example`, `requirements.txt`, and `.gitignore` adjusted for new tooling and generated paths.
- `scripts/format_docs_html.py` and `scripts/sync_docs.py` updated alongside the documentation pipeline.
- `docs/developer/0008-docs-pipeline.html` updated (versioning notes, pdoc output path `docs/api/`, optional CI).
- `scripts/changelog_draft.py` feeds commit messages, name-status paths, and a stronger system prompt so LLM changelog drafts reflect substance rather than diff stats only.


## [1.1.0] — 2026-04-10

### Added

- `PUT /api/v1/user/{system_user_id}` — full replacement of mutable profile fields with `Idempotency-Key` and validation codes `USER_014`–`USER_024`.
- `PATCH /api/v1/user/{system_user_id}` — partial update with `Idempotency-Key`; empty body returns `USER_PATCH_BODY_EMPTY` (`USER_102`); idempotency scope uses path prefix `PATCH /api/v1/user/...` (distinct from `PUT`).
- Changelog practice (ADR 0013), optional `scripts/changelog_draft.py`, and CI changelog gate for user-facing paths.

### Changed

- API / OpenAPI version **1.1.0** (see `app/main.py`).
