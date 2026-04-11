# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- ADR 0017: branch naming (`feature/`, `fix/`, `docs/`, `chore/`, `refactor/`), `main` as integration branch, release tags `v*.*.*`, and hotfix forward-port guidance.

## [1.1.1] — 2026-04-11

### Added

- ADR 0014: dead-code hygiene (Ruff F401/RUF100, Vulture, `make dead-code-check`, weekly workflow).
- ADR document `docs/adr/0013-changelog-and-release-notes.html` outlining changelog and release‑notes policy.
- New script `scripts/llm_client.py` providing an LLM client interface.
- New script `scripts/llm_ping.py` for health‑checking the LLM service.
- `Dockerfile`, `.dockerignore`, `scripts/container_entrypoint.sh`, and `k8s/` manifests (`namespace`, `deployment`, `service`, `configmap`, `pvc`, `secret.example.yaml`) for local Docker and Kubernetes workflows.
- README and developer guide clarify that Docker/Kubernetes are optional for daily development, and outline how real-world deploys typically use a registry and target environment.
- Developer guide [docs/developer/0009-docker-and-kubernetes-local.html](docs/developer/0009-docker-and-kubernetes-local.html) and ADR 0015 (container image and local Kubernetes).
- Makefile targets `docker-build`, `container-start` (same entrypoint script as Docker), `k8s-render-configmap`, and `k8s-apply`.
- `k8s/app.env` as the source for the generated `k8s/configmap.yaml` (`scripts/render_k8s_configmap.py`, wired into `make docs-fix`).
- ADR 0016 (Google-style Python docstrings, alignment with `make api-docs` / pdoc), developer index entry, and `.cursor/rules/python-docstrings.mdc` for editor guidance; expanded module docstrings across `app/`.

### Changed

- GitHub Actions quality job runs `make verify` (applies `docs-fix` on the runner) instead of `make verify-ci` / `docs-check`, avoiding false failures when generated docs drift from `HEAD`.
- Updated `CONTRIBUTING.md` with new contribution guidelines.
- Minor adjustments to `Makefile` for build and test targets.
- Updated `requirements.txt` to include dependencies required by the new LLM scripts.
- Refactored `scripts/changelog_draft.py` to integrate LLM generation logic and improve draft creation.
- `CHANGELOG.md`, `README.md`, and `CONTRIBUTING.md` updated for container/Kubernetes workflows and discovery of new docs.
- `docs/adr/README.html`, `docs/developer/README.html`, and `docs/engineering-practices.html` link to ADR 0015 and the Docker/Kubernetes developer guide.
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
