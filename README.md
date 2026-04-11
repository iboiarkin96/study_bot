# Study App API

FastAPI service for Study App domain workflows. Long-form documentation: [system analysis](docs/system-analysis.html), [engineering practices](docs/engineering-practices.html).

## Quick start

```bash
make venv && source .venv/bin/activate
make install
make env-init
make migrate
make run
```

- API docs (Swagger): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Full stack (API + Docker observability): `make run-project` instead of `make run` (see below).

---

## Observability (local)

Stack: **Prometheus**, **Grafana**, **Blackbox exporter** (`docker-compose.observability.yml`). Prometheus scrapes the API via `host.docker.internal:8000` (see `ops/prometheus/prometheus.tpl.yml` → rendered `ops/prometheus/prometheus.yml`).

### Default URLs

| What | URL | Notes |
| ---- | --- | ----- |
| API | [http://127.0.0.1:8000](http://127.0.0.1:8000) | `APP_HOST` / `APP_PORT` |
| Liveness / readiness / metrics | `/live`, `/ready`, `/metrics` | |
| Prometheus UI | [http://127.0.0.1:9090](http://127.0.0.1:9090) | [Targets](http://127.0.0.1:9090/targets) |
| Grafana | [http://127.0.0.1:3001](http://127.0.0.1:3001) | maps host **3001** → container 3000; login `admin` / `admin` |
| Blackbox exporter | [http://127.0.0.1:9115](http://127.0.0.1:9115) | probe metrics for Prometheus |
| Dashboard (imported) | [Study App Observability](http://127.0.0.1:3001/d/study-app-observability/study-app-observability?orgId=1) | Grafana |

Override host/port labels for docs and smoke checks: `OBS_API_*`, `OBS_PROM_*`, `OBS_GRAF_*` (see `env/example`).

### How to run it

1. Start the API: `make run` (or use `make run-project` to bring up Docker observability and then the API in one flow).
2. If the API is already running: `make observability-up` (renders Prometheus config, starts Compose).
3. Check `/live`, `/ready`, and `/metrics` (e.g. `curl -s http://127.0.0.1:8000/live`).
4. When finished: `make observability-down`. Optional link check: `make observability-smoke`.

More detail (ports, Blackbox, stopping containers): [Local development](docs/developer/0007-local-development.html). Architecture and SLO/error-budget context: [ADR 0009](docs/adr/0009-health-readiness-and-observability.html), [ADR 0011](docs/adr/0011-slo-sla-error-budget.html).

### Metrics useful in Prometheus / Grafana

Examples: `http_requests_total`, `http_request_duration_seconds_bucket`, `db_operation_duration_seconds_bucket`. Use the Grafana dashboard above for charts; in Prometheus UI use **Graph** and paste PromQL (e.g. `sum(rate(http_requests_total[1m]))` for overall RPS).

---

## Container image & local Kubernetes (optional)

Day-to-day development does **not** depend on Docker or Kubernetes: use **`make run`**, tests, and **`make verify`** as usual. The cycle (feature → tests → merge) stays the same.

**Why add Docker at all?** In most real environments the service runs as a **container image**: the same artifact is promoted through staging and production. Building an image (`make docker-build`) is the standard packaging step when you prepare a release or run in a remote environment. **Local Kubernetes** (`k8s/`, `make k8s-apply`) is optional — mainly for learning and for checking manifests; it is not required for every feature.

- **Prerequisites:** Docker (Desktop or Engine), `kubectl`, and a local cluster (Docker Desktop Kubernetes, minikube, or kind). Install links and options are in [§0 of the Docker & Kubernetes guide](docs/developer/0009-docker-and-kubernetes-local.html#prerequisites).
- **Docker:** `make docker-build` produces image `study-app-api:local` (see `Dockerfile`). The container runs `scripts/container_entrypoint.sh` (Alembic, then Uvicorn) — the same script as `make container-start` on the host (without `--reload`). Dependencies are the same pinned `requirements.txt` as `make install` (no second lockfile).
- **Kubernetes:** non-secret pod env is edited in **`k8s/app.env`** (single source); `make k8s-render-configmap` (also run from `make docs-fix`) regenerates `k8s/configmap.yaml`. Default profile is **`APP_ENV=dev`** — no API key Secret required. Then `make k8s-apply` and `kubectl -n study-app port-forward svc/study-app-api 8000:8000`.
- **Guide (optional tooling, real deploy outline, step-by-step):** [Docker & local Kubernetes](docs/developer/0009-docker-and-kubernetes-local.html). **ADRs:** [0015](docs/adr/0015-container-image-and-local-kubernetes.html) (container image), [0021](docs/adr/0021-continuous-delivery-github-actions-and-ghcr.html) (CI → GHCR). **Optional Secret for `qa`:** [k8s/secret.example.yaml](k8s/secret.example.yaml).

---

## Environment (`APP_ENV`)

The process reads **`APP_ENV`** (`dev`, `qa`, `prod`). Set it in **`.env`** or the host environment. **`GET /live`** includes `"app_env"` for a quick check.

| Path | Role |
| ---- | ---- |
| `env/example` | Committed template — copy to `.env` (`make env-init`). **All variables, defaults, and semantics are documented in this file** (single source of truth; not duplicated in the README). |
| `env/dev`, `env/qa`, `env/prod` | Optional profile overrides (merged automatically) |

**Load order (later wins):** root `.env` → `env/<APP_ENV>` → optional `ENV_FILE`.
Tests use **`APP_ENV=qa`**. Legacy `APP_ENV=test` is mapped to **`qa`**.

Useful: `make env-check`, `curl -s http://127.0.0.1:8000/live | jq`.

---

## Documentation

| Topic | Link |
| ----- | ---- |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |
| Contributing (verify, docs, OpenAPI, ADRs) | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Engineering practices & handbook | [engineering-practices.html](docs/engineering-practices.html) |
| System analysis & error matrix | [system-analysis.html](docs/system-analysis.html) |
| Developer guides (requirements, contracts, load testing, local dev, Docker/K8s) | [docs/developer/README.html](docs/developer/README.html) |
| ADRs | [docs/adr/README.html](docs/adr/README.html) |
| Runbooks | [docs/runbooks/README.html](docs/runbooks/README.html) |
| OpenAPI — static request validator (Swagger UI + Ajv, no network) | [docs/openapi-explorer.html](docs/openapi-explorer.html) |

Daily workflow: prefer `make` targets (`make help`). Common flows: `make fix`, `make verify`, `make release-check`. Before commit: `make pre-commit-check`. Docs sync: `make docs-fix`; verify: `make docs-check`.


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
│   ├── api/
│   │   └── app/
│   ├── assets/
│   ├── backlog/
│   ├── developer/  # Developer guides and onboarding
│   ├── openapi/
│   ├── runbooks/  # Operational troubleshooting guides
│   └── uml/  # PlantUML diagrams
│       ├── architecture/
│       ├── include/  # Shared PlantUML skin (merged at Kroki render)
│       ├── rendered/  # Rendered PNGs
│       └── sequences/  # Sequence diagram sources
├── k8s/  # Kubernetes manifests; k8s/app.env sources the generated ConfigMap
└── scripts/  # Dev & CI helper scripts
```
<!-- END:REPO_LAYOUT -->

---

## HTTP endpoints

<!-- BEGIN:HTTP_ENDPOINTS -->
| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/api/v1/user` | Create user |
| `GET` | `/api/v1/user/{system_uuid}/{system_user_id}` | Get user by system_uuid and system_user_id |
| `PATCH` | `/api/v1/user/{system_uuid}/{system_user_id}` | Partially update user by system_uuid and system_user_id |
| `PUT` | `/api/v1/user/{system_uuid}/{system_user_id}` | Update user by system_uuid and system_user_id |
| `GET` | `/docs` | Custom Swagger Ui |
| `GET` | `/live` | Liveness probe |
| `GET` | `/metrics` | Metrics Endpoint |
| `GET` | `/ready` | Readiness probe |
<!-- END:HTTP_ENDPOINTS -->

---

## License

MIT
