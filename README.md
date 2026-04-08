# Study App API

FastAPI service for Study App domain workflows.

`README` is intentionally short. Detailed documentation lives in `docs/system-analysis.html`
and `docs/engineering-practices.html`.

---

## Quick start

```bash
make venv
source .venv/bin/activate
make install
cp .env.example .env
make migrate
make run
```

Swagger:
- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Developer documentation

Primary sources: `docs/system-analysis.html`, `docs/engineering-practices.html`

- Developer entry point: [`docs/engineering-practices.html#developer-handbook`](docs/engineering-practices.html#developer-handbook)
- Non-functional requirements: [`docs/system-analysis.html#dev-nfr`](docs/system-analysis.html#dev-nfr)
- Error matrix and contracts: [`docs/system-analysis.html#dev-error-matrix`](docs/system-analysis.html#dev-error-matrix)
- Development workflow and quality gates: [`docs/engineering-practices.html#dev-guide`](docs/engineering-practices.html#dev-guide)
- Docs-as-code process: [`docs/engineering-practices.html#dev-docs-as-code`](docs/engineering-practices.html#dev-docs-as-code)
- API versioning policy: [`docs/engineering-practices.html#dev-versioning`](docs/engineering-practices.html#dev-versioning)
- ADR catalog: `docs/adr/`
- ADR index: `docs/adr/README.html`
- ADR template: `docs/adr/0000-template.html`
- Developer docs index: `docs/developer/README.html`
- Requirements guide: `docs/developer/0001-requirements.html`
- Schemas/contracts guide: `docs/developer/0002-schemas-and-contracts.html`
- Business logic guide: `docs/developer/0003-business-logic.html`
- Beginner guide (`POST /api/v1/contract` plan): `docs/developer/0004-how-to-add-post-contract.html`
- Runbooks index: `docs/runbooks/README.html`
- Runbook template: `docs/runbooks/0000-template.html`
- Pre-commit runbook: `docs/runbooks/0004-pre-commit-failing.html`
- Quality-check runbook: `docs/runbooks/0005-quality-check-failing.html`
- Runbook mini-SLA policy: `docs/runbooks/README.html`

Policy:
- Local operations are executed via `make` targets from `Makefile`.
- Docs HTML template normalization: `make docs-format` (included in `make sync-docs`).
- Before commit: `make pre-commit-check`
- Before PR/deploy: `make quality-check` and `make pre-deploy`

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
│   ├── services/  # Business logic
│   └── validation/
├── alembic/  # Migration environment
│   └── versions/  # Migration scripts
├── docs/  # HTML docs & UML sources
│   ├── adr/
│   ├── assets/
│   ├── developer/  # Developer guides and onboarding
│   ├── runbooks/  # Operational troubleshooting guides
│   └── uml/  # PlantUML diagrams
│       ├── architecture/
│       ├── rendered/  # Rendered PNGs
│       └── sequences/  # Sequence diagram sources
└── scripts/  # Dev & CI helper scripts
```
<!-- END:REPO_LAYOUT -->

---

## Configuration

Configuration is loaded from `.env` (based on `.env.example`).

<!-- BEGIN:CONFIG_TABLE -->
| Variable | Description | Example |
| -------- | ----------- | ------- |
| `APP_NAME` | Title shown in OpenAPI | `Study App API` |
| `APP_ENV` | Logical environment label | `local` |
| `APP_HOST` | Bind address for Uvicorn | `127.0.0.1` |
| `APP_PORT` | Listen port | `8000` |
| `SQLITE_DB_PATH` | SQLite database file (relative or absolute path) | `study_app.db` |
| `LOG_DIR` |  | `logs` |
| `LOG_FILE_NAME` |  | `app.log` |
| `LOG_LEVEL` |  | `INFO` |
<!-- END:CONFIG_TABLE -->

---

## HTTP endpoints

<!-- BEGIN:HTTP_ENDPOINTS -->
| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/api/v1/user` | Create user |
| `GET` | `/health` | Health check |
<!-- END:HTTP_ENDPOINTS -->

---

## License

MIT
