# ADR 0001: Adopt Docs as Code

## Status

Accepted

## Context

The API surface is expanding and requires consistent contracts, reliable onboarding, and reproducible documentation updates.
Manual documentation updates are error-prone and can drift from runtime behavior.

## Decision

Adopt Docs as Code as a mandatory engineering practice:

1. Keep documentation in repository and version it with code.
2. Treat OpenAPI contracts, error schemas, and examples as part of public API contract.
3. Use command-driven generation/synchronization for docs artifacts.
4. Enforce documentation checks in quality gates before deployment.

## Implementation in this repository

- Human docs:
  - `README.md`
  - `docs/index.html`
- Diagram sources:
  - `docs/uml/**/*.puml`
- Generated diagrams:
  - `docs/uml/rendered/*.png`
- Sync tooling:
  - `scripts/regenerate_docs.py`
  - `scripts/sync_docs.py`
- Make targets:
  - `make docs`
  - `make sync-docs`
  - `make docs-check`
  - `make pre-deploy`
  - `make deploy DEPLOY_CMD="..."`

## Consequences

### Positive

- Documentation remains aligned with runtime behavior.
- Changes are auditable in PR history.
- Release process blocks stale docs and missing generated artifacts.

### Trade-offs

- Slightly longer pre-release pipeline.
- Developers must run docs commands as part of regular workflow.

## Usage

Typical workflow:

```bash
make test
make docs
make sync-docs
make docs-check
make pre-deploy
```

