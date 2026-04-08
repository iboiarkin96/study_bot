# ADR 0003: Error Contract Governance

## Status

Accepted

## Context

As API endpoints grow, clients require stable and machine-readable error behavior.
Unstructured or inconsistent errors increase integration cost and make support/debugging harder.

## Decision

Adopt a governed, code-based error contract.

1. Error payloads are part of public API contract.
2. Use stable numeric `code` and symbolic `key`.
3. `code` + `key` are immutable once published.
4. Contract evolves additively; existing semantics cannot be silently changed.
5. Validation and business errors follow explicit, documented schemas.

## Contract model

- Business error shape:
  - `{"code":"...","key":"...","message":"...","source":"business"}`
- Validation error shape:
  - `{"error_type":"validation_error","endpoint":"...","errors":[...]}`
  - each `errors[]` item: `code`, `key`, `message`, `field`, `source`, `details`

## Implementation in this repository

- Validation mapping source:
  - `app/errors/validation.py`
- Error response schemas:
  - `app/schemas/errors.py`
- OpenAPI examples:
  - `app/openapi/examples/errors.py`
- Endpoint declarations:
  - router `responses={...}` in `app/api/v1/*.py`

## Consequences

### Positive

- Predictable client integration behavior.
- Better incident diagnostics and observability.
- Easier compatibility management across API versions.

### Trade-offs

- Requires governance discipline and documentation updates.
- Expanding error catalog requires ongoing curation.

## Operating rules

1. Add new codes; do not repurpose old ones.
2. Keep fallback validation codes for unmapped errors.
3. Update OpenAPI examples and docs in the same change.
4. Ensure `make docs-check` and `make pre-deploy` pass before release.

