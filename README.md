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

---

## Developer documentation

Primary sources: `docs/system-analysis.html`, `docs/engineering-practices.html`

- [Developer handbook](docs/engineering-practices.html#developer-handbook)
- [Error matrix](docs/system-analysis.html#dev-error-matrix)
- [Dev workflow](docs/engineering-practices.html#dev-guide)
- [Docs process](docs/engineering-practices.html#dev-docs-as-code)
- [API versioning](docs/engineering-practices.html#dev-versioning)
- [ADR index](docs/adr/README.html)
- [ADR idempotency policy](docs/adr/0006-idempotency-write-operations.html)
- [Developer docs](docs/developer/README.html), [requirements](docs/developer/0001-requirements.html), [schemas](docs/developer/0002-schemas-and-contracts.html), [logic](docs/developer/0003-business-logic.html), [beginner guide](docs/developer/0004-how-to-add-post-contract.html)
- [Runbooks](docs/runbooks/README.html), [template](docs/runbooks/0000-template.html), [pre-commit](docs/runbooks/0004-pre-commit-failing.html), [quality-check](docs/runbooks/0005-quality-check-failing.html), [api security](docs/runbooks/0006-api-security-failing.html)

Policy:
- Local operations are executed via `make` targets from `Makefile`.
- Use scenario entrypoints for daily work: `make fix`, `make verify`, `make release-check`, `make release DEPLOY_CMD='...'`.
- Atomic targets remain available for granular control (`format-*`, `lint-*`, `type-check`, `test*`, `docs-*`, `openapi-*`).
- Docs synchronization and HTML normalization: `make docs-fix`.
- Docs drift validation (no updates expected): `make docs-check`.
- Before commit: `make pre-commit-check`
- Before PR/deploy: `make verify` and `make release-check`

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
│   ├── openapi/
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
| `LOG_DIR` | Directory where app logs are written | `logs` |
| `LOG_FILE_NAME` | Application log filename | `app.log` |
| `LOG_LEVEL` | Root log level | `INFO` |
| `CORS_ALLOW_ORIGINS` | Allowed browser origins (CSV) | `http://127.0.0.1:3000,http://localhost:3000` |
| `CORS_ALLOW_METHODS` | Allowed CORS methods (CSV) | `GET,POST,PUT,PATCH,DELETE,OPTIONS` |
| `CORS_ALLOW_HEADERS` | Allowed CORS headers (CSV) | `Authorization,Content-Type,X-API-Key` |
| `CORS_ALLOW_CREDENTIALS` | Whether CORS credentials are allowed | `false` |
| `API_BODY_MAX_BYTES` | Maximum request body size in bytes | `1048576` |
| `API_RATE_LIMIT_REQUESTS` | Requests per window for one client+path | `60` |
| `API_RATE_LIMIT_WINDOW_SECONDS` | Rate-limit window in seconds | `60` |
| `API_AUTH_STRATEGY` | Auth mode (`mock_api_key` or `disabled`) | `mock_api_key` |
| `API_MOCK_API_KEY` | Mock API key value for local/dev | `local-dev-key` |
| `API_AUTH_HEADER` | Header name used for API key auth | `X-API-Key` |
| `API_PROTECTED_PREFIX` | URL prefix where auth/rate-limit are enforced | `/api/v1` |
<!-- END:CONFIG_TABLE -->

---

## HTTP endpoints

<!-- BEGIN:HTTP_ENDPOINTS -->
| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/api/v1/user` | Create user |
| `GET` | `/api/v1/user/{system_user_id}` | Get user by system_user_id |
| `GET` | `/docs` | Custom Swagger Ui |
| `GET` | `/health` | Health check |
<!-- END:HTTP_ENDPOINTS -->

---

## License

MIT
