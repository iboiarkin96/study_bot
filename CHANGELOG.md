# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- ADR 0014: dead-code hygiene (Ruff F401/RUF100, Vulture, `make dead-code-check`, weekly workflow).

## [1.1.0] — 2026-04-10

### Added

- `PUT /api/v1/user/{system_user_id}` — full replacement of mutable profile fields with `Idempotency-Key` and validation codes `USER_014`–`USER_024`.
- `PATCH /api/v1/user/{system_user_id}` — partial update with `Idempotency-Key`; empty body returns `USER_PATCH_BODY_EMPTY` (`USER_102`); idempotency scope uses path prefix `PATCH /api/v1/user/...` (distinct from `PUT`).
- Changelog practice (ADR 0013), optional `scripts/changelog_draft.py`, and CI changelog gate for user-facing paths.

### Changed

- API / OpenAPI version **1.1.0** (see `app/main.py`).
