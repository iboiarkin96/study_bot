# ADR 0002: Mandatory API Testing Policy

## Status

Accepted

## Context

API surface is expanding and contract regressions become more expensive without automated checks.
Manual verification is insufficient for stable delivery and predictable releases.

## Decision

Adopt mandatory endpoint-level automated testing as a release gate.

1. Any API change must include tests.
2. Endpoint coverage must include at least:
   - one success scenario (happy path),
   - one failure scenario (validation or business error).
3. Changes without tests are considered incomplete.
4. Quality gates must enforce test execution before deployment.

## Implementation in this repository

- Test framework: `pytest`
- Test location: `tests/`
- API baseline tests:
  - `tests/api/v1/test_users_register.py`
- Make targets:
  - `make test`
  - `make test-one path=...`
  - `make pre-deploy` (includes tests)
  - `make deploy DEPLOY_CMD="..."` (always runs pre-deploy first)

## Consequences

### Positive

- Early regression detection.
- Higher confidence in API contract stability.
- Faster onboarding with executable behavior examples.

### Trade-offs

- Additional implementation effort for each change.
- Slightly longer pipeline execution time.

## Usage

Typical flow:

```bash
make test
make test-one path=tests/api/v1/test_users_register.py
make pre-deploy
```

