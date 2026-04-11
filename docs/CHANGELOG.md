# Documentation changelog

All notable changes to the **documentation tree** under `docs/` (and related doc-only policy files) are tracked here. This journal is separate from the repository root [`CHANGELOG.md`](../CHANGELOG.md), which focuses on product and API behavior (see [ADR 0013](adr/0013-changelog-and-release-notes.html)).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- [ADR 0022](adr/0022-embedded-swagger-ui-openapi-sandbox.html) superseded: browser validation cancelled; `openapi-explorer.html` is OpenAPI (test), Swagger browse-only; task on hold. Removed `openapi-live.html` (use app `/docs` for Try it out).

### Added

- [ADR 0021](adr/0021-continuous-delivery-github-actions-and-ghcr.html): continuous delivery via GitHub Actions — build <code>Dockerfile</code>, push to GHCR after CI, beginner-oriented context (CI vs CD), scope, and references; developer guide <a href="developer/0009-docker-and-kubernetes-local.html">0009</a> links to registry automation.

- [ADR 0019](adr/0019-python-dependency-security-pip-audit-and-pinning-policy.html): Python dependency security—`requirements.txt` as exact pin, `pip-audit`, Make/CI expectations, severity handling, and exception process (implements backlog policy; `make deps-audit` / CI wiring tracked there).

- Documentation changelog (`docs/CHANGELOG.md`) and ADR lifecycle policy ([ADR 0018](adr/0018-adr-lifecycle-ratification-and-badges.html)): Issue discussion with `[ADR]` title, ratification via Issue + PR, `data-adr-weight`, and `docs/CHANGELOG.md` update expectations.

- [ADR 0020](adr/0020-c4-plantuml-diagram-style-and-conventions.html): C4 views, PlantUML layout and naming conventions, and a shared diagram style via `docs/uml/include/style.puml` (with `docs/uml/README.txt` for authors).

### Changed

- All numbered ADRs (`0001`–`0017`): replaced legacy **Status** badge blocks with `data-adr-weight="7"` on `<main>` and a **Ratification** note for pre–ADR-0018 adoption; UI status comes from `docs/assets/docs-nav.js` per [ADR 0018](adr/0018-adr-lifecycle-ratification-and-badges.html). [ADR 0018](adr/0018-adr-lifecycle-ratification-and-badges.html) and [ADR 0019](adr/0019-python-dependency-security-pip-audit-and-pinning-policy.html) include the collapsible weight help from the [ADR template](adr/0000-template.html).

- ADR template: weight instructions in a collapsible `<details class="adr-weight-help">` (styles in `docs/assets/docs.css`); `data-adr-weight` default for new drafts is `-1` (not `9`, which clamped to `7`).

- ADR **Status log**: one attribute on `<main>` — `data-adr-weight` (−1…7); **current status** and the linear 8-step log derive from that value. [ADR template](adr/0000-template.html), [ADR 0018](adr/0018-adr-lifecycle-ratification-and-badges.html), `docs/assets/docs-nav.js`, `docs/assets/docs.css`.

- API reference generation: `scripts/normalize_pdoc_output.py` strips unstable `at 0x…` fragments from pdoc HTML so `make docs-check` stays reproducible; `make api-docs` runs with `PYTHONHASHSEED=0`.

- PlantUML under `docs/uml/`: architecture and sequence `.puml` sources include the shared style; rendered PNGs in `docs/uml/rendered/` updated to match ([ADR 0020](adr/0020-c4-plantuml-diagram-style-and-conventions.html)).

- Docs pipeline and contributor entrypoints: `scripts/regenerate_docs.py`, `scripts/sync_docs.py`, `Makefile`, `CONTRIBUTING.md`, and `.github/ISSUE_TEMPLATE/adr_discussion.md` aligned with ADR lifecycle, UML rendering, and synced HTML companions (`docs/engineering-practices.html`, `docs/system-analysis.html`, `docs/backlog/README.html`, `docs/runbooks/README.html`, `docs/developer/0008-docs-pipeline.html`).
