## Summary

- What changed and why?
- What behavior is affected?

## Change type

- [ ] `delivery` (feature/API/code behavior change)
- [ ] `docs-only` (documentation structure/content/navigation only)
- [ ] `mixed` (both code and docs)

## Golden path checklist

### For `delivery`

- [ ] Requirements/contract implications reviewed (OpenAPI, schemas, errors, versioning).
- [ ] Implementation is complete across required layers.
- [ ] OpenAPI/internal docs updated in the same PR when behavior changed.
- [ ] Local gate passed: `make verify`.
- [ ] Pre-push gate passed: `make verify-ci`.

### For `docs-only`

- [ ] Document type and structure validated against `docs/internal/front/documentation-style-guide.html`.
- [ ] Related hubs/indexes/cross-links updated where needed.
- [ ] Internal docs layout/sidebar consistency verified (when `docs/internal/` changed).
- [ ] Docs normalization passed: `make docs-fix`.
- [ ] Docs drift/validation passed: `make docs-check`.

## Audit and conformance

- [ ] I validated terminology consistency and naming conventions across affected pages.
- [ ] I checked links/navigation for changed or new docs pages.
- [ ] I reviewed this PR against `docs/internal/front/documentation-style-guide.html`.
- [ ] If policy/process changed, I updated related ADR/RFC/docs references in this PR.

## Testing notes

- Commands run:
  - `...`
- Key output or evidence:
  - `...`

## Changelog

- [ ] Updated `CHANGELOG.md` (user-facing changes).
- [ ] Updated `docs/CHANGELOG.md` (documentation-facing changes).
- [ ] No changelog update needed (`[skip changelog]` rationale is explicit).
