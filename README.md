# Study App API

REST API for user registration and related domain logic. Built with **FastAPI**, **SQLAlchemy 2**, **Alembic**, and **SQLite**, with configuration from environment variables and request/response validation via **Pydantic v2**.

---

## Table of contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Running the server](#running-the-server)
- [API documentation (Swagger)](#api-documentation-swagger)
- [HTTP endpoints](#http-endpoints)
- [Non-functional requirements](#non-functional-requirements)
- [Error matrix](#error-matrix)
- [Development guide](#development-guide)
- [Testing policy (mandatory)](#testing-policy-mandatory)
- [Database and migrations](#database-and-migrations)
- [Project documentation (HTML & UML)](#project-documentation-html--uml)
- [Docs as Code workflow](#docs-as-code-workflow)
- [Documentation generation workflow](#documentation-generation-workflow)
- [Makefile reference](#makefile-reference)
- [Git](#git)

---

## Features

- Environment-based config (`.env` + `python-dotenv`)
- Layered structure: routers → services → repositories → ORM models
- Alembic migrations for schema evolution
- OpenAPI / Swagger UI out of the box
- Pydantic validation on API payloads

---

## Tech stack

| Layer        | Technology                          |
| ------------ | ----------------------------------- |
| Web framework| FastAPI                             |
| ASGI server  | Uvicorn                             |
| ORM          | SQLAlchemy 2.x                      |
| Migrations   | Alembic                             |
| Database     | SQLite (file path from env)         |
| Validation   | Pydantic v2                         |
| HTTP client (dev) | httpx (for TestClient)       |

---

## Repository layout

<!-- BEGIN:REPO_LAYOUT -->
```text
study_app/
├── app/  # Application package
│   ├── api/  # HTTP layer
│   │   └── v1/  # v1 routers
│   ├── core/  # Settings, DB session
│   ├── errors/
│   ├── models/  # ORM models
│   │   ├── core/  # Core domain entities
│   │   └── reference/  # Reference / lookup entities
│   ├── openapi/
│   │   └── examples/
│   ├── repositories/  # Data-access layer
│   ├── schemas/  # Pydantic request/response models
│   └── services/  # Business logic
├── alembic/  # Migration environment
│   └── versions/  # Migration scripts
├── docs/  # HTML docs & UML sources
│   ├── adr/
│   └── uml/  # PlantUML diagrams
│       ├── architecture/
│       ├── rendered/  # Rendered PNGs
│       └── sequences/  # Sequence diagram sources
└── scripts/  # Dev & CI helper scripts
```
<!-- END:REPO_LAYOUT -->

---

## Prerequisites

- **Python** 3.11 or newer (tested with 3.14)
- **make** (optional but recommended; all common tasks are wrapped in the `Makefile`)

---

## Getting started

1. Clone the repository (or open the project folder).
2. Create and activate a virtual environment

```bash
make venv
source .venv/bin/activate
```

3. Install dependencies

```bash
make install
```

4. Configure environment

```bash
cp .env.example .env
# Edit .env: especially SQLITE_DB_PATH, APP_HOST, APP_PORT
```

5. Apply database migrations

```bash
make migrate
```

6. Start the API

```bash
make run
```

The server reads `APP_HOST` and `APP_PORT` from `.env` (see [Configuration](#configuration)).

---

## Configuration

Variables are loaded from `.env` in the project root (see `app/core/config.py`).

<!-- BEGIN:CONFIG_TABLE -->
| Variable | Description | Example |
| -------- | ----------- | ------- |
| `APP_NAME` | Title shown in OpenAPI | `Study App API` |
| `APP_ENV` | Logical environment label | `local` |
| `APP_HOST` | Bind address for Uvicorn | `127.0.0.1` |
| `APP_PORT` | Listen port | `8000` |
| `SQLITE_DB_PATH` | SQLite database file (relative or absolute path) | `study_app.db` |
<!-- END:CONFIG_TABLE -->

> **Security:** do not commit `.env` with secrets. The repository includes `.env.example` only. Local `*.db` files are listed in `.gitignore`.

---

## API documentation (Swagger)

After the server is up:

| Resource    | URL |
| ----------- | --- |
| **Swagger UI** | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (use your `APP_HOST`/`APP_PORT` if different) |
| **ReDoc**      | [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc) |

Interactive docs include request schemas, response models, and validation rules generated from Pydantic.

---

## HTTP endpoints

<!-- BEGIN:HTTP_ENDPOINTS -->
| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/api/v1/users/register` | Register user |
| `GET` | `/health` | Health check |
<!-- END:HTTP_ENDPOINTS -->

---

## Non-functional requirements

These requirements are mandatory for implementation and release decisions.

| Category | Requirement |
| -------- | ----------- |
| Performance | Typical API requests should complete in under 300 ms with local DB and light load; avoid N+1 and excessive serialization in hot paths. |
| Reliability | Write operations are transactional, rollback on failure is mandatory, and error responses must follow stable contracts. |
| Maintainability | Layering stays explicit (router -> service -> repository); endpoint behavior is covered by automated tests. |
| Extensibility | New interfaces/channels are added through adapters without rewriting business logic core. |
| API contract governance | OpenAPI schemas/examples/error contracts are public API; evolution is additive, no silent breaking changes. |
| Validation consistency | All external input is validated at API boundary and normalized into code-based error payloads. |
| Security baseline | Secrets are never committed; deployment uses environment-managed secrets. |
| Observability readiness | Logs and error payloads are structured enough for diagnosis and support. |
| Release quality gate | Deployment requires successful `make pre-deploy` pipeline. |
| Documentation governance | README and `docs/index.html` are updated together; generated sections remain sync-safe. |

Reference:
- Human-readable architecture/requirements page: `docs/index.html` (section "Non-Functional Requirements").

---

## Error matrix

This repository uses a code-based error contract.  
Error Matrix documents the **approach and extension rules**, not an exhaustive list of every code.

### Error contract (project standard)

- **Business errors (`4xx`)** return:
  - `{"code":"...","key":"...","message":"...","source":"business"}`
- **Validation errors (`422`)** return:
  - `{"error_type":"validation_error","endpoint":"...","errors":[...]}`
  - each item in `errors[]`: `code`, `key`, `message`, `field`, `source`, `details`

### Where error matrix lives

- **Validation code catalog:** `app/errors/validation.py`
- **OpenAPI error examples:** `app/openapi/examples/errors.py`
- **Error schemas (contract):** `app/schemas/errors.py`
- **Endpoint declarations (`responses`):** `app/api/v1/*.py`
- **Human-readable matrix summary:** this `README.md` and `docs/index.html`

### How to extend matrix safely

1. Add new code mapping in `app/errors/validation.py` (or endpoint-specific mapper).
2. Add/update OpenAPI examples in `app/openapi/examples/errors.py`.
3. Ensure endpoint `responses={...}` references correct models/examples.
4. Update summary in `README.md` and `docs/index.html`.
5. Do not change semantic meaning of existing `code`/`key` pairs.

---

## Development guide

### 1) Project philosophy
- API contract is the product: request/response/error schemas are always current and versioned by code.
- Documentation is part of delivery: endpoint behavior and docs evolve in the same change.
- One source of truth per concern: validation mapping, examples, and schemas are centralized.

### 2) Validation standards (general)
- Validate all external input at API boundary (Pydantic schemas/types/validators).
- Keep business/service layer free from duplicate shape validation.
- Normalize validation failures into stable error codes and keys.
- Return errors in a consistent machine-readable contract.

### 3) Error-code governance
- `code` + `key` are immutable public contract.
- Additive evolution only: add new codes, do not repurpose old ones.
- Keep fallback code path for unmapped validation failures.
- Every new endpoint should define explicit error `responses` in Swagger.

### 4) Documentation discipline
- OpenAPI (`/docs`) must match runtime behavior and examples.
- Update matrix summary when adding new error families/endpoints.
- Keep docs concise: list approach and extension rules; full code catalog stays in source files.

### 5) Scalability checklist
- New endpoint has request/response schemas, examples, and error responses.
- Validation mapper covers endpoint-specific error family.
- Error examples are present and readable in Swagger.
- Tests exist for at least one happy-path and one failure-path per endpoint.
- No endpoint change is considered done without tests.
- Pre-deploy quality gate (`make pre-deploy`) passes before any deployment action.
- `make sync-docs` runs cleanly and does not overwrite manual sections unexpectedly.

---

## Testing policy (mandatory)

Tests are a release gate in this project.

- Every API change must include tests; changes without tests are considered incomplete.
- For each endpoint, keep at least:
  - one success scenario test,
  - one validation/business failure scenario test.
- Keep tests deterministic and isolated (independent DB state per test run).

Commands:

```bash
make test
make test-one path=tests/api/v1/test_users_register.py
make pre-deploy
make deploy DEPLOY_CMD="echo Deploying to staging"
```

Pre-deploy gate (`make pre-deploy`) runs mandatory sequence:
1. Environment check (`make check`)
2. Test suite (`make test`)
3. UML regeneration (`make docs`)
4. Documentation sync (`make sync-docs`)

Deployment wrapper:
- `make deploy DEPLOY_CMD="..."` always runs `make pre-deploy` first.
- Actual deployment is delegated to `DEPLOY_CMD` so infra-specific steps stay configurable.

Current baseline:
- API tests live in `tests/`.
- Example endpoint coverage is implemented for `POST /api/v1/users/register`.

---

## Project documentation (HTML & UML)

- Human-readable requirements and diagrams: open **`docs/index.html`** in a browser.
- PlantUML sources live under `docs/uml/`:
  - `docs/uml/architecture/*.puml` - C4 architecture views
  - `docs/uml/sequences/*.puml` - sequence diagrams
- Rendered PNGs are stored in `docs/uml/rendered/`.
- To regenerate all UML images:

  ```bash
  make docs
  make docs-watch   # watch docs/uml/**/*.puml and regenerate on changes
  ```

### Publish docs to GitHub Pages

Repository includes workflow: `.github/workflows/publish-docs.yml`.

How to enable:
1. In repository settings open **Pages**.
2. Set source to **GitHub Actions**.
3. Push to `main`/`master` (or run workflow manually from Actions tab).

What workflow does:
- builds docs (`make docs`, `make sync-docs`);
- verifies docs integrity (`make docs-check`);
- publishes `docs/` as static site via GitHub Pages.

Result:
- you get a rendered docs URL from workflow output (`github-pages` environment URL),
- page opens as full HTML (not raw source), unlike repository file preview.

---

## Docs as Code workflow

Documentation is treated as a first-class artifact, same as source code.

### Source-of-truth model

- Business and transport behavior: `app/`
- Error code mapping: `app/errors/validation.py`
- OpenAPI examples: `app/openapi/examples/`
- UML source diagrams: `docs/uml/**/*.puml`
- Engineering decisions (ADR): `docs/adr/*.md`
- Generated docs sections: marker blocks in `README.md` and `docs/index.html`

### Daily usage

```bash
# during development
make test
make docs
make sync-docs

# before PR / deploy
make pre-deploy
```

### Docs quality checks

`make docs-check` verifies that:
- rendered UML files are up to date (`scripts/regenerate_docs.py --check`);
- marker-managed docs sections are synchronized (`scripts/sync_docs.py --check`).

If it fails, run:

```bash
make docs
make sync-docs
```

### PR rule

- API changes are incomplete without:
  - tests,
  - updated OpenAPI contracts/examples,
  - synchronized docs (`make sync-docs`),
  - passing docs checks (`make docs-check`).

---

## Documentation generation workflow

This project has **two independent doc-generation flows**:

1. **Diagram rendering flow** (`make docs`, `make docs-watch`)
   - Source of truth: `docs/uml/**/*.puml`
   - Output: `docs/uml/rendered/*.png`
   - Script: `scripts/regenerate_docs.py`

2. **Text sync flow** (`make sync-docs`)
   - Sources of truth:
     - `Makefile` (command reference)
     - `app.main` routes (HTTP endpoints)
     - `.env.example` (configuration table)
     - repository directory structure
   - Outputs:
     - `README.md` sections between `<!-- BEGIN:... -->` and `<!-- END:... -->`
     - API contracts block in `docs/index.html` (`API_CONTRACTS`)
   - Script: `scripts/sync_docs.py`

Recommended update sequence after architecture/API/doc changes:

```bash
make docs
make sync-docs
```

Important:
- Edit only content **outside** auto-generated marker blocks if you want manual text to persist.
- Marker blocks are managed by scripts and may be overwritten on the next sync.

---

## Makefile reference

<!-- BEGIN:MAKEFILE_REF -->
| Command | Purpose |
| ------- | ------- |
| `make venv` | Create virtual environment |
| `make install` | Install dependencies |
| `make requirements` | Auto-generate requirements.txt from .venv |
| `make run` | Start FastAPI dev server |
| `make migrate` | Apply all Alembic migrations |
| `make migration name=…` | Auto-generate new Alembic migration |
| `make docs` | Regenerate UML docs once |
| `make docs-watch` | Watch UML sources, regenerate on change |
| `make docs-check` | Verify generated docs are up to date |
| `make test` | Run full test suite (pytest) |
| `make test-one path=…` | Run one test file or node |
| `make pre-deploy` | Run full quality gate before deploy |
| `make deploy DEPLOY_CMD='…'` | Run pre-deploy then deploy command |
| `make check` | Verify env, deps, and DB connectivity |
| `make sync-docs` | Auto-update README.md & docs/index.html from code |
<!-- END:MAKEFILE_REF -->


---

## License

MIT
