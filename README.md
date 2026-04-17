# Study App API

FastAPI service for Study App domain workflows. Long-form documentation: [System design](docs/internal/system-design.html), [Developers Docs](docs/internal/developers.html), [architecture & quality assessments](docs/audit/README.html).

## Contents

| Section | What you get |
| ------- | ------------ |
| [Quick start](#quick-start) | Install, migrate, run the API locally |
| [Environment and configuration](#environment-and-configuration) | `APP_ENV`, `.env`, profile files |
| [Documentation and workflows](#documentation-and-workflows) | Changelog, guides, ADRs, Make entrypoints |
| [Observability (local)](#observability-local) | Prometheus, Grafana, metrics, optional Elasticsearch/Kibana |
| [Container image and Kubernetes (optional)](#container-image-and-local-kubernetes-optional) | Docker image, local cluster |
| [Repository layout](#repository-layout) | Top-level tree |
| [HTTP endpoints](#http-endpoints) | OpenAPI reference (`docs/api`) |
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

👉**API + Docker observability in one flow:** `make run-project` instead of `make run` (details under [Observability](#observability-local)).

---

## Environment and configuration

The process reads **`APP_ENV`** (`dev`, `qa`, `prod`). Set it in **`.env`** or the host environment. **`GET /live`** includes `"app_env"` for a quick check.

| Path | Role |
| ---- | ---- |
| `env/example` | Committed template — copy to `.env` (`make env-init`). **All variables, defaults, and semantics are documented in this file** (single source of truth; not duplicated in the README). |
| `env/dev`, `env/qa`, `env/prod` | Optional profile overrides (merged automatically) |

**Load order (later wins):** root `.env` → `env/<APP_ENV>` → optional `ENV_FILE`.
Tests use **`APP_ENV=qa`**. Legacy `APP_ENV=test` is mapped to **`qa`**.

Useful: `make env-check`, `curl -s http://127.0.0.1:8000/live | jq`.

---

## Documentation and workflows

**Full docs** is located at `docs/index.html`.

**Daily workflow:** prefer `make` targets (`make help`).
1) Common flows: `make fix`, `make verify`, `make verify-ci` before push, `make release-check`.
2) Before commit: `make pre-commit-check`. Docs sync: `make docs-fix`; strict sync check: `make docs-check`.


---

## Observability (local)

Stack: **Prometheus**, **Grafana**, **Blackbox exporter** (`docker-compose.observability.yml`). Prometheus scrapes the API via `host.docker.internal:8000` (see `ops/prometheus/prometheus.tpl.yml` → rendered `ops/prometheus/prometheus.yml`).

### Default URLs

| What | URL | Notes |
| ---- | --- | ----- |
| Prometheus UI | [http://127.0.0.1:9090](http://127.0.0.1:9090) | [Targets](http://127.0.0.1:9090/targets) |
| Grafana | [http://127.0.0.1:3001](http://127.0.0.1:3001) | maps host **3001** → container 3000; login `admin` / `admin` |
| Blackbox exporter | [http://127.0.0.1:9115](http://127.0.0.1:9115) | probe metrics for Prometheus |
| Dashboard (imported) | [<abbr title="Extract–Transform–Retrieve">ETR</abbr> Study API Observability](http://127.0.0.1:3001/d/study-app-observability/study-app-observability?orgId=1) | Grafana |

Override host/port labels for docs and smoke checks: `OBS_API_*`, `OBS_PROM_*`, `OBS_GRAF_*` (see `env/example`).

### How to run it

1. Start the API: `make run` (or use `make run-project` to bring up Docker observability and then the API in one flow).
2. If the API is already running: `make observability-up` (renders Prometheus config, starts Compose).
3. Check `/live`, `/ready`, and `/metrics` (e.g. `curl -s http://127.0.0.1:8000/live`).
4. When finished: `make observability-down`. Optional link check: `make observability-smoke`.

More detail (ports, Blackbox, stopping containers): [Local development](docs/developer/0007-local-development.html). Architecture and SLO/error-budget context: [ADR 0009](docs/adr/0009-health-readiness-and-observability.html), [ADR 0011](docs/adr/0011-slo-sla-error-budget.html).

### Structured logs and Elasticsearch (optional)

For **NDJSON** logs and local **search/analytics**, use `LOG_FORMAT=json` and `LOG_SERVICE_NAME` (see `env/example`; **json is the default** when `LOG_FORMAT` is unset). Uvicorn’s duplicate access log is disabled (`--no-access-log`); correlation uses **`request_id`** in `app.main` **request_done** lines. Every response includes an **`X-Request-Id`** header; JSON lines include `request_id`, and `trace_id` / `span_id` are reserved (null until OpenTelemetry).

| What | URL | Notes |
| ---- | --- | ----- |
| Elasticsearch | [http://127.0.0.1:9200](http://127.0.0.1:9200) | REST API; indices `study-app-logs-*` (see Kibana note) |
| Kibana | [http://127.0.0.1:5601](http://127.0.0.1:5601) | Data view index pattern **`*study-app-logs*`** (wildcards on both sides) — **not** only `study-app-logs-*`, or Discover may miss `.ds-study-app-logs-*` data streams |

**Flow:** `make logging-up` starts `docker-compose.logging.yml` (Elasticsearch, Kibana, Filebeat). The API should run on the host with `LOG_FORMAT=json` writing to `./logs` (mounted read-only into Filebeat). **~2 GiB RAM** recommended for ES+Kibana. `make logging-smoke` checks ES/Kibana; `make logging-down` stops the stack. Details and licensing notes: [ADR 0023](docs/adr/0023-structured-logging-and-local-elasticsearch.html).

### Metrics useful in Prometheus / Grafana

Examples: `http_requests_total`, `http_request_duration_seconds_bucket`, `db_operation_duration_seconds_bucket`. Use the Grafana dashboard above for charts; in Prometheus UI use **Graph** and paste PromQL (e.g. `sum(rate(http_requests_total[1m]))` for overall RPS).

---

## Container image and local Kubernetes (optional)

Day-to-day development does **not** depend on Docker or Kubernetes: use **`make run`**, tests, and **`make verify`** as usual. The cycle (feature → tests → merge) stays the same.

**Why add Docker at all?** In most real environments the service runs as a **container image**: the same artifact is promoted through staging and production. Building an image (`make docker-build`) is the standard packaging step when you prepare a release or run in a remote environment. **Local Kubernetes** (`k8s/`, `make k8s-apply`) is optional — mainly for learning and for checking manifests; it is not required for every feature.

- **Prerequisites:** Docker (Desktop or Engine), `kubectl`, and a local cluster (Docker Desktop Kubernetes, minikube, or kind). Install links and options are in the [Docker & Kubernetes guide — Prerequisites](docs/developer/0009-docker-and-kubernetes-local.html#prerequisites).
- **Docker:** `make docker-build` produces image `study-app-api:local` (see `Dockerfile`). The container runs `scripts/container_entrypoint.sh` (Alembic, then Uvicorn) — the same script as `make container-start` on the host (without `--reload`). Dependencies are the same pinned `requirements.txt` as `make install` (no second lockfile).
- **Kubernetes:** non-secret pod env is edited in **`k8s/app.env`** (single source); `make k8s-render-configmap` (also run from `make docs-fix`) regenerates `k8s/configmap.yaml`. Default profile is **`APP_ENV=dev`** — no API key Secret required. Then `make k8s-apply` and `kubectl -n study-app port-forward svc/study-app-api 8000:8000`.
- **Guide (optional tooling, real deploy outline, step-by-step):** [Docker & local Kubernetes](docs/developer/0009-docker-and-kubernetes-local.html). **ADRs:** [0015](docs/adr/0015-container-image-and-local-kubernetes.html) (container image), [0021](docs/adr/0021-continuous-delivery-github-actions-and-ghcr.html) (CI → GHCR). **Optional Secret for `qa`:** [k8s/secret.example.yaml](k8s/secret.example.yaml).

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
│   ├── api/
│   │   └── app/
│   ├── assets/
│   ├── audit/
│   ├── backlog/
│   ├── developer/  # Developer guides and onboarding
│   ├── howto/
│   ├── internal/
│   │   └── api/
│   ├── openapi/
│   ├── runbooks/  # Operational troubleshooting guides
│   └── uml/  # PlantUML diagrams
│       ├── architecture/
│       ├── include/  # Shared PlantUML skin (merged at Kroki render)
│       ├── make/
│       ├── rendered/  # Rendered PNGs
│       └── sequences/  # Sequence diagram sources
├── k8s/  # Kubernetes manifests; k8s/app.env sources the generated ConfigMap
├── ops/  # Prometheus, Grafana, Filebeat configs
│   ├── filebeat/  # Filebeat → Elasticsearch (local logging stack)
│   ├── grafana/  # Dashboards and provisioning
│   └── prometheus/  # Scrape config, rules, Blackbox
└── scripts/  # Dev & CI helper scripts
```
<!-- END:REPO_LAYOUT -->

---

## HTTP endpoints

The full HTTP API, including all endpoints, schemas, and example requests and responses, is documented separately with OpenAPI. To browse the API reference, see: [docs/api/index.html](docs/api/index.html)

---

## License

MIT
