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
make env-init
make migrate
make run
```

Swagger:
- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Observability quick start (beginner-friendly)

1) Start the API:
```bash
make run
```

2) Check probes and metrics endpoint:
```bash
curl http://127.0.0.1:8000/live
curl http://127.0.0.1:8000/ready
curl http://127.0.0.1:8000/metrics
```

3) Start Prometheus + Grafana:
```bash
make observability-up
```

4) Open tools in browser:
- Prometheus: [http://127.0.0.1:9090](http://127.0.0.1:9090)
  - Targets: [http://127.0.0.1:9090/targets](http://127.0.0.1:9090/targets)
- Grafana: [http://127.0.0.1:3001](http://127.0.0.1:3001)
  - Dashboard (Study App Observability): [http://127.0.0.1:3001/d/study-app-observability/study-app-observability?orgId=1](http://127.0.0.1:3001/d/study-app-observability/study-app-observability?orgId=1)
  - login: `admin` / `admin`

Hosts used in local monitoring:
- API app: `127.0.0.1:8000`
- Prometheus UI: `127.0.0.1:9090`
- Grafana UI: `127.0.0.1:3001`
- Prometheus scrape target from Docker: `host.docker.internal:8000` (template `ops/prometheus/prometheus.tpl.yml`, rendered into `ops/prometheus/prometheus.yml`)
- You can override these via env: `OBS_API_HOST`, `OBS_API_PORT`, `OBS_PROM_HOST`, `OBS_PROM_PORT`, `OBS_GRAF_HOST`, `OBS_GRAF_PORT`.

5) Generate traffic so graphs move:
```bash
for i in {1..20}; do curl -s http://127.0.0.1:8000/live > /dev/null; done
for i in {1..20}; do curl -s http://127.0.0.1:8000/ready > /dev/null; done
```

6) Verify key metrics in Prometheus:
- `http_requests_total`
- `http_request_duration_seconds_bucket`
- `db_operation_duration_seconds_bucket`

Ready-to-open Prometheus queries:
- Request rate (RPS): [http://127.0.0.1:9090/graph?g0.expr=sum%28rate%28http_requests_total%5B1m%5D%29%29&g0.tab=0](http://127.0.0.1:9090/graph?g0.expr=sum%28rate%28http_requests_total%5B1m%5D%29%29&g0.tab=0)
- Error rate (%): [http://127.0.0.1:9090/graph?g0.expr=100%20*%20sum%28rate%28http_requests_total%7Bstatus_code%3D~%225..%7C4..%22%7D%5B5m%5D%29%29%20%2F%20sum%28rate%28http_requests_total%5B5m%5D%29%29&g0.tab=0](http://127.0.0.1:9090/graph?g0.expr=100%20*%20sum%28rate%28http_requests_total%7Bstatus_code%3D~%225..%7C4..%22%7D%5B5m%5D%29%29%20%2F%20sum%28rate%28http_requests_total%5B5m%5D%29%29&g0.tab=0)
- API latency p95 (ms): [http://127.0.0.1:9090/graph?g0.expr=1000%20*%20histogram_quantile%280.95%2C%20sum%28rate%28http_request_duration_seconds_bucket%5B5m%5D%29%29%20by%20%28le%29%29&g0.tab=0](http://127.0.0.1:9090/graph?g0.expr=1000%20*%20histogram_quantile%280.95%2C%20sum%28rate%28http_request_duration_seconds_bucket%5B5m%5D%29%29%20by%20%28le%29%29&g0.tab=0)
- DB latency p95 (ms): [http://127.0.0.1:9090/graph?g0.expr=1000%20*%20histogram_quantile%280.95%2C%20sum%28rate%28db_operation_duration_seconds_bucket%5B5m%5D%29%29%20by%20%28le%29%29&g0.tab=0](http://127.0.0.1:9090/graph?g0.expr=1000%20*%20histogram_quantile%280.95%2C%20sum%28rate%28db_operation_duration_seconds_bucket%5B5m%5D%29%29%20by%20%28le%29%29&g0.tab=0)

7) Stop observability stack when done:
```bash
make observability-down
```

Optional smoke-check of monitoring links:
```bash
make observability-smoke
```

### Configuration and environments (`APP_ENV`)

**Which stand am I on?** The process reads **`APP_ENV`** (`dev`, `qa`, or `prod`). Set it in **`.env`** on your laptop, or in the **host environment** in production (container / systemd / platform config). **`GET /live`** returns JSON with `"app_env"` so you can verify the running profile without guessing.

**Repository layout (tracked):**

| Path | Role |
| ---- | ---- |
| `env/example` | **Only** committed template — copy once to `.env` (`make env-init`) or `cp env/example .env` |
| `env/dev`, `env/qa`, `env/prod` | Small overrides for that profile (optional; merged automatically) |

**Load order (later wins):**

1. `.env` in the project root (your secrets and `APP_ENV=…`)
2. `env/<APP_ENV>` (e.g. `env/dev` when `APP_ENV=dev`)
3. Optional `ENV_FILE` (absolute path or path relative to project root) for secrets / host-specific files

Automated tests force **`APP_ENV=qa`** (same governance rules as QA). Legacy value `APP_ENV=test` is accepted and mapped to **`qa`**.

**Useful commands:** `make env-check` (loads config and prints effective DB path), `curl -s http://127.0.0.1:8000/live | jq` (see `app_env`).

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
- [Runbooks](docs/runbooks/README.html), [template](docs/runbooks/0000-template.html), [pre-commit](docs/runbooks/0004-pre-commit-failing.html), [quality-check](docs/runbooks/0005-quality-check-failing.html), [api security](docs/runbooks/0006-api-security-failing.html), [openapi contract-test](docs/runbooks/0007-openapi-contract-test-failing.html), [observability scrape](docs/runbooks/0008-observability-scrape-failing.html)

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

Configuration is loaded from `.env` (create it from `env/example`). See **Configuration and environments** above.

<!-- BEGIN:CONFIG_TABLE -->
| Variable | Description | Example |
| -------- | ----------- | ------- |
| `APP_NAME` | Title shown in OpenAPI | `Study App API` |
| `APP_ENV` | Logical environment label | `dev` |
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
| `METRICS_ENABLED` |  | `true` |
| `METRICS_PATH` |  | `/metrics` |
| `READINESS_DB_TIMEOUT_MS` |  | `250` |
| `METRICS_BUCKETS_HTTP` |  | `0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2.5,5` |
| `METRICS_BUCKETS_DB` |  | `0.001,0.0025,0.005,0.01,0.025,0.05,0.1,0.25` |
| `OBS_API_HOST` |  | `127.0.0.1` |
| `OBS_API_PORT` |  | `8000` |
| `OBS_PROM_HOST` |  | `127.0.0.1` |
| `OBS_PROM_PORT` |  | `9090` |
| `OBS_GRAF_HOST` |  | `127.0.0.1` |
| `OBS_GRAF_PORT` |  | `3001` |
| `PROMETHEUS_PORT` |  | `9090` |
| `GRAFANA_PORT` |  | `3001` |
| `PROMETHEUS_SCRAPE_TARGET` |  | `host.docker.internal:8000` |
| `GRAFANA_ADMIN_USER` |  | `admin` |
| `GRAFANA_ADMIN_PASSWORD` |  | `admin` |
<!-- END:CONFIG_TABLE -->

---

## HTTP endpoints

<!-- BEGIN:HTTP_ENDPOINTS -->
| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/api/v1/user` | Create user |
| `GET` | `/api/v1/user/{system_user_id}` | Get user by system_user_id |
| `GET` | `/docs` | Custom Swagger Ui |
| `GET` | `/live` | Liveness probe |
| `GET` | `/metrics` | Metrics Endpoint |
| `GET` | `/ready` | Readiness probe |
<!-- END:HTTP_ENDPOINTS -->

---

## License

MIT
