# <abbr title="Extract–Transform–Retrieve">ETR</abbr> Study App API

FastAPI service for the Study App domain. Longer reads: [System design](docs/internal/analysis/system-design.html), [Developers](docs/developer/README.html), [Architecture & quality assessments](docs/audit/README.html).

## Contents

| Section | What you find |
| ------- | ------------- |
| [Quick start](#quick-start) | Install, migrate, run the API locally |
| [Environment and configuration](#environment-and-configuration) | `APP_ENV`, `.env`, profile files |
| [Documentation and workflows](#documentation-and-workflows) | Changelog, guides, ADRs, Make commands |
| [Observability (local)](#observability-local) | Prometheus, Grafana, metrics, optional Elasticsearch/Kibana |
| [Container image (optional)](#container-image-optional) | Docker image, `docker run` |
| [Repository layout](#repository-layout) | Top-level tree |
| [HTTP endpoints](#http-endpoints) | OpenAPI (`docs/openapi/`: baseline JSON + static Swagger UI), Python API (`docs/pdoc/`) |
| [License](#license) | MIT |

---

## Quick start

```bash
make venv && source .venv/bin/activate
make install
make env-init
make migrate
make run
```

Use `make setup` once, then `make dev` for day-to-day work.

---

## Environment and configuration

The app reads **`APP_ENV`** (`dev`, `qa`, or `prod`). Set it in **`.env`** or in the shell. **`GET /live`** returns `"app_env"` so you can confirm the value quickly.

| Path | Role |
| ---- | ---- |
| `env/example` | Template you copy to `.env` (`make env-init`). **All variables, defaults, and meanings are documented only here** (not repeated in this README). |
| `env/dev`, `env/qa`, `env/prod` | Optional profile files (merged on top of the base) |

**Order of loading (last wins):** root `.env` → `env/<APP_ENV>` → optional `ENV_FILE`.

Tests use **`APP_ENV=qa`**. The old value **`APP_ENV=test`** is treated as **`qa`**.

Helpful: `make env-check`, `curl -s http://127.0.0.1:8000/live | jq`.

---

## Documentation and workflows

The main documentation site is **`docs/index.html`**.

**Daily work:** use **`make`** targets (`make help` lists them).

1. Common: `make fix`, `make check` during development, and `make verify` before you push.
2. Before commit: `make pre-commit-check`. After doc edits: `make docs-fix`. To check that nothing is missing: `make docs-check`.

---

## Observability (local)

Stack: **Prometheus**, **Grafana**, **Blackbox exporter** (`docker-compose.observability.yml`). Prometheus scrapes the API at `host.docker.internal:8000` (see `ops/prometheus/prometheus.tpl.yml` → `ops/prometheus/prometheus.yml`).

### Default URLs

| What | URL | Notes |
| ---- | --- | ----- |
| Prometheus UI | [http://127.0.0.1:9090](http://127.0.0.1:9090) | [Targets](http://127.0.0.1:9090/targets) |
| Grafana | [http://127.0.0.1:3001](http://127.0.0.1:3001) | Host port **3001** → container 3000; login `admin` / `admin` |
| Blackbox exporter | [http://127.0.0.1:9115](http://127.0.0.1:9115) | Probe metrics for Prometheus |
| Dashboard (imported) | [<abbr title="Extract–Transform–Retrieve">ETR</abbr> Study API Observability](http://127.0.0.1:3001/d/study-app-observability/study-app-observability?orgId=1) | Grafana |

For docs and smoke checks you can override host/port labels: `OBS_API_*`, `OBS_PROM_*`, `OBS_GRAF_*` (see `env/example`).

### How to run it

1. Start the API: `make run`.
2. If the API is already running and you need observability, start Docker Compose manually: `docker compose -f docker-compose.observability.yml up -d`.
3. Check `/live`, `/ready`, and `/metrics` (e.g. `curl -s http://127.0.0.1:8000/live`).
4. When you are done: `docker compose -f docker-compose.observability.yml down`.

More detail: [Local development](docs/developer/0007-local-development.html). Design notes: [ADR 0009](docs/adr/0009-health-readiness-and-observability.html), [ADR 0011](docs/adr/0011-slo-sla-error-budget.html).

### Structured logs and Elasticsearch (optional)

For **NDJSON** logs and local **search**, set `LOG_FORMAT=json` and `LOG_SERVICE_NAME` (see `env/example`; **json is the default** if `LOG_FORMAT` is unset). Uvicorn’s extra access log is off (`--no-access-log`). Correlation uses **`request_id`** in **request_done** lines in `app.main`. Every response sends **`X-Request-Id`**; JSON lines include `request_id`. `trace_id` / `span_id` are reserved (null until OpenTelemetry is added).

| What | URL | Notes |
| ---- | --- | ----- |
| Elasticsearch | [http://127.0.0.1:9200](http://127.0.0.1:9200) | REST API; indices `study-app-logs-*` |
| Kibana | [http://127.0.0.1:5601](http://127.0.0.1:5601) | Data view: pattern **`*study-app-logs*`** (wildcards on both sides). Not only `study-app-logs-*`, or Discover may miss `.ds-study-app-logs-*` streams |

**Steps:** start `docker-compose.logging.yml` manually (`docker compose -f docker-compose.logging.yml up -d`). Run the API on the host with `LOG_FORMAT=json` writing to `./logs` (mounted read-only into Filebeat). **~2 GiB RAM** helps for ES+Kibana. Stop with `docker compose -f docker-compose.logging.yml down`. Details: [ADR 0023](docs/adr/0023-structured-logging-and-local-elasticsearch.html).

### Metrics in Prometheus / Grafana

Examples: `http_requests_total`, `http_request_duration_seconds_bucket`, `db_operation_duration_seconds_bucket`. Use the Grafana dashboard above for charts; in Prometheus use **Graph** and PromQL (e.g. `sum(rate(http_requests_total[1m]))` for RPS).

---

## Container image (optional)

You do **not** need Docker for day-to-day coding: use **`make run`**, tests, and **`make verify`**.

**Why Docker still matters:** in many deployments the service runs as a **container image**. Building it with `docker build` is the normal packaging step for a release or a registry pull.

- **Prerequisites:** [Docker](https://docs.docker.com/get-docker/) if you build or run the image locally.
- **Build and run:** `docker build -t study-app-api:local .` builds image `study-app-api:local` (see `Dockerfile`). The container runs `scripts/container_entrypoint.sh` (Alembic, then Uvicorn, no `--reload`). Dependencies match pinned `requirements.txt` from `make install`. Pass configuration with `-e` or your platform’s env mechanism (see `env/example`).
- **Guide:** [Docker image and container](docs/developer/0009-docker-image-and-container.html). **ADRs:** [0015](docs/adr/0015-container-image.html) (image), [0021](docs/adr/0021-continuous-delivery-github-actions-and-ghcr.html) (CI → GHCR).

---

## Repository layout

<!-- BEGIN:REPO_LAYOUT -->
```text
study_app/
├── docker-compose.observability.yml  # Prometheus, Grafana, Blackbox
├── docker-compose.logging.yml  # Optional: Elasticsearch, Kibana, Filebeat
├── app/  # Application package
│   ├── api/  # HTTP layer
│   │   └── v1/  # v1 routers
│   ├── core/  # Settings, DB session
│   ├── domain/
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
│   ├── audit/
│   │   ├── api/
│   │   ├── bugs/
│   │   └── docs/
│   ├── backlog/
│   ├── developer/  # Developer guides and onboarding
│   ├── howto/
│   ├── internal/
│   │   ├── analysis/
│   │   ├── api/
│   │   ├── front/
│   │   ├── manager/
│   │   └── portal/
│   ├── openapi/
│   ├── pdoc/
│   │   └── app/
│   ├── qa/
│   │   ├── playbooks/
│   │   ├── reference/
│   │   └── templates/
│   ├── rfc/
│   ├── runbooks/  # Operational troubleshooting guides
│   └── uml/  # PlantUML diagrams
│       ├── architecture/
│       ├── include/  # Shared PlantUML skin (merged at Kroki render)
│       ├── make/
│       ├── rendered/  # Rendered SVGs
│       └── sequences/  # Sequence diagram sources
├── ops/  # Prometheus, Grafana, Filebeat configs
│   ├── filebeat/  # Filebeat → Elasticsearch (local logging stack)
│   ├── grafana/  # Dashboards and provisioning
│   └── prometheus/  # Scrape config, rules, Blackbox
└── scripts/  # Dev & CI helper scripts
```
<!-- END:REPO_LAYOUT -->

---

## HTTP endpoints

The HTTP API (endpoints, schemas, examples) is documented with OpenAPI. In `docs/openapi/`, the committed contract is [`openapi-baseline.json`](docs/openapi/openapi-baseline.json) and the static browse-only Swagger UI is [`index.html`](docs/openapi/index.html). Python modules (pdoc): [`docs/pdoc/index.html`](docs/pdoc/index.html).

---

## License

MIT
