PYTHON := .venv/bin/python
PIP    := .venv/bin/pip
ENV    := .env
DEPLOY_CMD ?=
PYTEST_FLAGS ?= -q --disable-warnings
NO_COLOR ?= 0
MAKEFLAGS += --no-print-directory

ifeq ($(NO_COLOR),1)
COLOR_RESET :=
COLOR_GREEN :=
COLOR_RED   :=
COLOR_CYAN  :=
else
COLOR_RESET := \033[0m
COLOR_GREEN := \033[32m
COLOR_RED   := \033[31m
COLOR_CYAN  := \033[36m
endif

ICON_OK   := $(COLOR_GREEN)✓$(COLOR_RESET)
ICON_ERR  := $(COLOR_RED)✗$(COLOR_RESET)
ICON_STEP := $(COLOR_CYAN)→$(COLOR_RESET)
ICON_INFO := $(COLOR_CYAN)i$(COLOR_RESET)

.PHONY: help venv install requirements env-init run run-loadtest-api run-loadtest-api-serve run-project migrate migration format-fix format-check lint-check lint-fix type-check openapi-check contract-test openapi-accept-changes fix verify verify-ci release-check release pre-commit-install pre-commit-check test test-one test-warnings env-check docs-fix docs-check observability-up observability-down observability-smoke

# ──────────────────────────────────────────────
# Help
# ──────────────────────────────────────────────
help:
	@echo ""
	@echo "  Study App — available commands"
	@echo "  ------------------------------------------------"
	@echo ""
	@echo "  Scenario flows (recommended entry points)"
	@echo "  make fix                    # apply auto-fixes before local run"
	@echo "  make verify                 # run local quality gate (docs auto-sync)"
	@echo "  make verify-ci              # CI gate: same as verify but docs-check (no doc writes)"
	@echo "  make release-check          # run full release gate"
	@echo "  make release DEPLOY_CMD='…' # release gate + deploy command"
	@echo ""
	@echo "  Atomic commands"
	@echo ""
	@echo "  # Environment"
	@echo "  make venv                 Create virtual environment"
	@echo "  make install              Install dependencies"
	@echo "  make requirements         Auto-generate requirements.txt from .venv"
	@echo "  make env-init             Create .env from env/example (once per machine)"
	@echo ""
	@echo "  # Application"
	@echo "  make run                  Start FastAPI dev server"
	@echo "  make run-loadtest-api     Start API (high rate limit) → run tools.load_testing.runner → stop"
	@echo "  make run-loadtest-api-serve  Like run, but high API rate limit (foreground; use in 2nd terminal with runner)"
	@echo "  make run-project          Start observability stack (Prometheus/Grafana/…) + FastAPI"
	@echo ""
	@echo "  # Database / Migrations"
	@echo "  make migrate              Apply all Alembic migrations"
	@echo "  make migration name=…     Auto-generate new Alembic migration"
	@echo ""
	@echo "  # Code Formatting"
	@echo "  make format-fix           Auto-format Python code"
	@echo "  make format-check         Verify code formatting (no changes)"
	@echo ""
	@echo "  # Linting"
	@echo "  make lint-fix             Run Ruff with auto-fixes"
	@echo "  make lint-check           Run Ruff lint checks"
	@echo ""
	@echo "  # Type Checking"
	@echo "  make type-check           Run mypy type checks"
	@echo ""
	@echo "  # OpenAPI Contract Governance"
	@echo "  make openapi-check        Lint (operationId, summary, write+422 examples) + breaking-change"
	@echo "                            guard vs docs/openapi/openapi-baseline.json (semantic: catches"
	@echo "                            removals and new required bits; additive compatible changes may pass)"
	@echo "  make contract-test        Stricter: generated OpenAPI must equal baseline JSON exactly"
	@echo "                            (any drift fails; use openapi-accept-changes after review)"
	@echo "  make openapi-accept-changes  Overwrite baseline with current app.openapi() (commit the file)"
	@echo ""
	@echo "  # Environment Health"
	@echo "  make env-check            Verify env, deps, and DB connectivity"
	@echo ""
	@echo "  # Quality Gates"
	@echo "  make fix                  Run auto-fixes (format-fix + lint-fix + docs-fix)"
	@echo "  make verify               Run lint-check + type-check + openapi-check + contract-test + test + docs-fix"
	@echo "  make verify-ci            Run lint-check + type-check + openapi-check + contract-test + test + docs-check"
	@echo ""
	@echo "  # Tests"
	@echo "  make test                 Run full test suite (pytest + coverage per pyproject.toml)"
	@echo "  make test-one path=…      Run one test file or node"
	@echo "  make test-warnings        Run tests with full warning details"
	@echo ""
	@echo "  # Documentation"
	@echo "  make docs-fix             Auto-update docs (UML + marker sync + html render + html format)"
	@echo "  make docs-check           Verify docs are already in sync (fails on drift)"
	@echo ""
	@echo "  # Observability (Prometheus + Grafana)"
	@echo "  make observability-up     Start Prometheus/Grafana stack with Docker Compose"
	@echo "  make observability-down   Stop Prometheus/Grafana stack"
	@echo "  make observability-smoke  Check observability links return HTTP 200"
	@echo ""
	@echo "  # Pre-commit Hooks"
	@echo "  make pre-commit-install   Install git pre-commit hooks"
	@echo "  make pre-commit-check     Run all pre-commit hooks"
	@echo ""
	@echo "  # Deployment"
	@echo "  make release-check        Run env-check + verify before deploy"
	@echo "  make release DEPLOY_CMD='…' Run release-check then deploy command"
	@echo ""

# ──────────────────────────────────────────────
# Environment
# ──────────────────────────────────────────────
# Create local virtual environment if it does not exist.
venv:
	@if [ -d ".venv" ]; then \
		printf "$(ICON_OK) %s\n" ".venv already exists"; \
	else \
		printf "$(ICON_STEP) %s\n" "Creating virtual environment…"; \
		python3 -m venv .venv && printf "$(ICON_OK) %s\n" ".venv created"; \
	fi

# Install project dependencies into .venv.
install:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Upgrading pip…"
	@$(PYTHON) -m pip install --upgrade pip -q
	@printf "$(ICON_STEP) %s\n" "Installing requirements…"
	@$(PIP) install -r requirements.txt -q
	@printf "$(ICON_OK) %s\n" "Dependencies installed"

# Freeze current .venv dependencies to requirements.txt.
requirements:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Generating requirements.txt from current .venv…"
	@$(PIP) freeze | LC_ALL=C sort > requirements.txt
	@printf "$(ICON_OK) %s\n" "requirements.txt updated"

# Create root .env from the single tracked template (env/example).
env-init:
	@if [ -f ".env" ]; then \
		printf "$(ICON_ERR) %s\n" ".env already exists — remove or rename it first."; exit 1; \
	fi
	@cp env/example .env && printf "$(ICON_OK) %s\n" ".env created from env/example — edit APP_ENV and secrets"

# ──────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────
# Start FastAPI app with values from .env.
run:
	@if [ ! -f "$(ENV)" ]; then \
		printf "$(ICON_ERR) %s\n" "$(ENV) not found. Run 'make env-init' (or cp env/example .env)."; exit 1; \
	fi
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Starting server (reading $(ENV))…"
	@set -a; . ./$(ENV); set +a; \
	APP_HOST=$${APP_HOST:-127.0.0.1}; \
	APP_PORT=$${APP_PORT:-8000}; \
	$(PYTHON) -m uvicorn app.main:app --host "$$APP_HOST" --port "$$APP_PORT" --reload

# Start API with high rate limits, wait for /ready, run tools.load_testing.runner, stop API.
# Asks for confirmation (server is temporary; port must be free). CI: LOADTEST_SKIP_CONFIRM=1
# Optional: LOADTEST_TOTAL_REQUESTS=200 LOADTEST_DELAY_MS=0 LOADTEST_RUNNER_EXTRA='--verbose'
# Defaults in .env: LOADTEST_DEFAULT_TOTAL_REQUESTS, LOADTEST_DEFAULT_DELAY_MS (see env/example)
# Script: tools/load_testing/run_with_local_api.sh
run-loadtest-api:
	@if [ ! -f "$(ENV)" ]; then \
		printf "$(ICON_ERR) %s\n" "$(ENV) not found. Run 'make env-init' (or cp env/example .env)."; exit 1; \
	fi
	@if [ ! -f ".venv/bin/python" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "run-loadtest-api: start API → runner → stop (see tools/load_testing/run_with_local_api.sh)"
	@ENV_FILE="$(ENV)" bash "$(CURDIR)/tools/load_testing/run_with_local_api.sh"

# Start API like `run`, but override rate limits for local load testing (long-running; run runner in another shell).
# Defaults: API_RATE_LIMIT_REQUESTS_LOADTEST=1000000000 API_RATE_LIMIT_WINDOW_SECONDS_LOADTEST=60
run-loadtest-api-serve:
	@if [ ! -f "$(ENV)" ]; then \
		printf "$(ICON_ERR) %s\n" "$(ENV) not found. Run 'make env-init' (or cp env/example .env)."; exit 1; \
	fi
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Starting server (loadtest rate limits; dev machine only)…"
	@set -a; . ./$(ENV); set +a; \
	export API_RATE_LIMIT_REQUESTS="$${API_RATE_LIMIT_REQUESTS_LOADTEST:-1000000000}"; \
	export API_RATE_LIMIT_WINDOW_SECONDS="$${API_RATE_LIMIT_WINDOW_SECONDS_LOADTEST:-60}"; \
	printf "$(ICON_INFO) %s\n" "API_RATE_LIMIT_REQUESTS=$$API_RATE_LIMIT_REQUESTS API_RATE_LIMIT_WINDOW_SECONDS=$$API_RATE_LIMIT_WINDOW_SECONDS"; \
	APP_HOST=$${APP_HOST:-127.0.0.1}; \
	APP_PORT=$${APP_PORT:-8000}; \
	$(PYTHON) -m uvicorn app.main:app --host "$$APP_HOST" --port "$$APP_PORT" --reload

# Start Docker observability stack, then FastAPI (foreground). Requires Docker.
run-project: observability-up run

# ──────────────────────────────────────────────
# Database / Migrations
# ──────────────────────────────────────────────
# Apply all Alembic migrations to current database.
migrate:
	@if [ ! -f "$(ENV)" ]; then \
		printf "$(ICON_ERR) %s\n" "$(ENV) not found. Cannot resolve SQLITE_DB_PATH."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Applying migrations…"
	@$(PYTHON) -m alembic upgrade head && printf "$(ICON_OK) %s\n" "Migrations applied"

# Generate a new Alembic migration from model diff.
migration:
	@if [ -z "$(name)" ]; then \
		echo ""; \
		printf "$(ICON_ERR) %s\n" "Missing migration name."; \
		echo ""; \
		echo "  Usage:"; \
		echo "    make migration name=full_name_of_migration"; \
		echo ""; \
		exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Generating migration '$(name)'…"
	@$(PYTHON) -m alembic revision --autogenerate -m "$(name)" && printf "$(ICON_OK) %s\n" "Migration created"

# ──────────────────────────────────────────────
# Docs
# ──────────────────────────────────────────────
# Code quality
# ──────────────────────────────────────────────
# Auto-format Python codebase.
format-fix:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Formatting Python code..."
	@$(PYTHON) -m ruff format .
	@printf "$(ICON_OK) %s\n" "Formatting completed"

# Check that formatting is already compliant.
format-check:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Checking Python code formatting..."
	@$(PYTHON) -m ruff format --check .
	@printf "$(ICON_OK) %s\n" "Formatting check passed"

# Run Ruff lint checks (no auto-fix).
lint-check:
	@printf "$(COLOR_CYAN)== LINT-CHECK: START ==$(COLOR_RESET)\n"
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Running Ruff lint checks..."
	@$(PYTHON) -m ruff check .
	@printf "$(ICON_OK) %s\n" "Lint checks passed"
	@printf "$(COLOR_GREEN)== LINT-CHECK: SUCCESS ==$(COLOR_RESET)\n"

# Run Ruff with automatic fixes where possible.
lint-fix:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Running Ruff auto-fixes..."
	@$(PYTHON) -m ruff check --fix .
	@printf "$(ICON_OK) %s\n" "Auto-fix pass completed"

# Run mypy static type checks.
type-check:
	@printf "$(COLOR_CYAN)== TYPE-CHECK: START ==$(COLOR_RESET)\n"
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Running mypy type checks..."
	@$(PYTHON) -m mypy app tests scripts
	@printf "$(ICON_OK) %s\n" "Type checks passed"
	@printf "$(COLOR_GREEN)== TYPE-CHECK: SUCCESS ==$(COLOR_RESET)\n"

# Lint current spec + compare to baseline for backward-incompatible API changes only
# (see scripts/openapi_governance.py: run_lint, run_breaking_check).
openapi-check:
	@printf "$(COLOR_CYAN)== OPENAPI-CHECK: START ==$(COLOR_RESET)\n"
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Running OpenAPI governance checks..."
	@$(PYTHON) scripts/openapi_governance.py check
	@printf "$(ICON_OK) %s\n" "OpenAPI checks passed"
	@printf "$(COLOR_GREEN)== OPENAPI-CHECK: SUCCESS ==$(COLOR_RESET)\n"

# Full-document equality: app.openapi() must match parsed baseline JSON (any diff fails)
# (see scripts/openapi_governance.py: run_snapshot_check).
contract-test:
	@printf "$(COLOR_CYAN)== CONTRACT-TEST: START ==$(COLOR_RESET)\n"
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Running OpenAPI snapshot contract test..."
	@$(PYTHON) scripts/openapi_governance.py contract-test
	@printf "$(ICON_OK) %s\n" "OpenAPI contract-test passed"
	@printf "$(COLOR_GREEN)== CONTRACT-TEST: SUCCESS ==$(COLOR_RESET)\n"

# Accept intentional OpenAPI changes by refreshing baseline snapshot.
openapi-accept-changes:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Accepting OpenAPI changes (updating baseline)..."
	@$(PYTHON) scripts/openapi_governance.py update-baseline
	@printf "$(ICON_OK) %s\n" "OpenAPI baseline updated"

# Run local auto-fix pipeline.
fix:
	@printf "$(COLOR_CYAN)== FIX: START ==$(COLOR_RESET)\n"
	@printf "$(ICON_INFO) %s\n" "[1/3] format-fix"
	@$(MAKE) format-fix
	@printf "$(ICON_INFO) %s\n" "[2/3] lint-fix"
	@$(MAKE) lint-fix
	@printf "$(ICON_INFO) %s\n" "[3/3] docs-fix"
	@$(MAKE) docs-fix
	@printf "$(COLOR_GREEN)== FIX: SUCCESS ==$(COLOR_RESET)\n"

# Run full local quality gate (lint, types, openapi, contract, tests, docs sync).
verify:
	@printf "$(COLOR_CYAN)== VERIFY: START ==$(COLOR_RESET)\n"
	@printf "$(ICON_INFO) %s\n" "[1/6] lint-check"
	@$(MAKE) lint-check
	@printf "$(ICON_INFO) %s\n" "[2/6] type-check"
	@$(MAKE) type-check
	@printf "$(ICON_INFO) %s\n" "[3/6] openapi-check"
	@$(MAKE) openapi-check
	@printf "$(ICON_INFO) %s\n" "[4/6] contract-test"
	@$(MAKE) contract-test
	@printf "$(ICON_INFO) %s\n" "[5/6] test"
	@$(MAKE) test
	@printf "$(ICON_INFO) %s\n" "[6/6] docs-fix"
	@$(MAKE) docs-fix
	@printf "$(COLOR_GREEN)== VERIFY: SUCCESS ==$(COLOR_RESET)\n"

# Same as verify but fails if docs are out of sync (for CI; does not write docs).
verify-ci:
	@printf "$(COLOR_CYAN)== VERIFY-CI: START ==$(COLOR_RESET)\n"
	@printf "$(ICON_INFO) %s\n" "[1/6] lint-check"
	@$(MAKE) lint-check
	@printf "$(ICON_INFO) %s\n" "[2/6] type-check"
	@$(MAKE) type-check
	@printf "$(ICON_INFO) %s\n" "[3/6] openapi-check"
	@$(MAKE) openapi-check
	@printf "$(ICON_INFO) %s\n" "[4/6] contract-test"
	@$(MAKE) contract-test
	@printf "$(ICON_INFO) %s\n" "[5/6] test"
	@$(MAKE) test
	@printf "$(ICON_INFO) %s\n" "[6/6] docs-check"
	@$(MAKE) docs-check
	@printf "$(COLOR_GREEN)== VERIFY-CI: SUCCESS ==$(COLOR_RESET)\n"

# Install git pre-commit hooks for local checks.
pre-commit-install:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Installing pre-commit hooks..."
	@$(PYTHON) -m pre_commit install
	@printf "$(ICON_OK) %s\n" "pre-commit hooks installed"

# Execute all pre-commit hooks against repository files.
pre-commit-check:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Running pre-commit hooks..."
	@$(PYTHON) -m pre_commit run --all-files
	@printf "$(ICON_OK) %s\n" "pre-commit checks passed"

# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────
# Run full pytest test suite.
test:
	@printf "$(COLOR_CYAN)== TEST: START ==$(COLOR_RESET)\n"
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Running tests..."
	@$(PYTHON) -m pytest $(PYTEST_FLAGS)
	@printf "$(ICON_OK) %s\n" "Tests passed"
	@printf "$(COLOR_GREEN)== TEST: SUCCESS ==$(COLOR_RESET)\n"

# Run selected pytest path or node.
test-one:
	@if [ -z "$(path)" ]; then \
		echo ""; \
		printf "$(ICON_ERR) %s\n" "Missing test path."; \
		echo ""; \
		echo "  Usage:"; \
		echo "    make test-one path=tests/api/v1/test_user_create.py"; \
		echo ""; \
		exit 1; \
	fi
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Running selected tests: $(path)"
	@$(PYTHON) -m pytest $(PYTEST_FLAGS) $(path)
	@printf "$(ICON_OK) %s\n" "Selected tests passed"

# Run pytest with warning details enabled (for warning investigation).
test-warnings:
	@printf "$(COLOR_CYAN)== TEST-WARNINGS: START ==$(COLOR_RESET)\n"
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Running tests with warning details..."
	@$(PYTHON) -m pytest -q -rA
	@printf "$(COLOR_GREEN)== TEST-WARNINGS: SUCCESS ==$(COLOR_RESET)\n"

# Run mandatory release gate (env-check + verify).
release-check:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(COLOR_CYAN)== RELEASE-CHECK: START ==$(COLOR_RESET)\n"
	@printf "$(ICON_INFO) %s\n" "[1/2] env-check"
	@$(MAKE) env-check
	@printf "$(ICON_INFO) %s\n" "[2/2] verify"
	@$(MAKE) verify
	@printf "$(COLOR_GREEN)== RELEASE-CHECK: SUCCESS ==$(COLOR_RESET)\n"

# Run deploy command after successful release-check gate.
release:
	@if [ -z "$(DEPLOY_CMD)" ]; then \
		echo ""; \
		printf "$(ICON_ERR) %s\n" "Missing DEPLOY_CMD."; \
		echo ""; \
		echo "  Usage:"; \
		echo "    make release DEPLOY_CMD='echo Deploying to staging'"; \
		echo ""; \
		exit 1; \
	fi
	@printf "$(COLOR_CYAN)== RELEASE: START ==$(COLOR_RESET)\n"
	@$(MAKE) release-check
	@printf "$(ICON_STEP) %s\n" "Running deploy command: $(DEPLOY_CMD)"
	@sh -c "$(DEPLOY_CMD)"
	@printf "$(COLOR_GREEN)== RELEASE: SUCCESS ==$(COLOR_RESET)\n"

# ──────────────────────────────────────────────
# Docs
# ──────────────────────────────────────────────
# Regenerate docs artifacts and normalize docs HTML.
docs-fix:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@if [ ! -f "scripts/regenerate_docs.py" ]; then \
		printf "$(ICON_ERR) %s\n" "scripts/regenerate_docs.py not found."; exit 1; \
	fi
	@printf "$(COLOR_CYAN)== DOCS-FIX: START ==$(COLOR_RESET)\n"
	@printf "$(ICON_INFO) %s\n" "[1/3] regenerate UML diagrams"
	@$(PYTHON) scripts/regenerate_docs.py
	@printf "$(ICON_INFO) %s\n" "[2/3] sync marker-based documentation"
	@$(PYTHON) scripts/sync_docs.py
	@printf "$(ICON_INFO) %s\n" "[3/4] render docs markdown to html companions"
	@$(PYTHON) scripts/render_docs_html.py
	@printf "$(ICON_INFO) %s\n" "[4/4] normalize docs html template"
	@$(PYTHON) scripts/format_docs_html.py
	@printf "$(COLOR_GREEN)== DOCS-FIX: SUCCESS ==$(COLOR_RESET)\n"

# Verify docs are already synchronized (no drift allowed).
# Compare the full working tree diff vs HEAD before and after docs-fix. If identical,
# docs-fix did not change any file—so committed generated artifacts match the pipeline.
# (Local edits in unrelated paths are preserved as long as docs-fix leaves the tree unchanged.)
docs-check:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@tmp_before=$$(mktemp); tmp_after=$$(mktemp); \
	git diff HEAD > "$$tmp_before"; \
	$(MAKE) docs-fix; \
	git diff HEAD > "$$tmp_after"; \
	if cmp -s "$$tmp_before" "$$tmp_after"; then \
		printf "$(ICON_OK) %s\n" "Docs check passed (no drift)"; \
		rm -f "$$tmp_before" "$$tmp_after"; \
	else \
		printf "$(ICON_ERR) %s\n" "Docs drift detected. Run 'make docs-fix' and commit updated files."; \
		rm -f "$$tmp_before" "$$tmp_after"; \
		exit 1; \
	fi

# Start local Prometheus + Grafana observability stack.
observability-up:
	@printf "$(ICON_STEP) %s\n" "Starting observability stack..."
	@$(PYTHON) scripts/render_prometheus_config.py
	@docker compose -f docker-compose.observability.yml up -d
	@printf "$(ICON_OK) %s\n" "Observability stack is up (Prometheus:9090, Grafana:3001, Blackbox:9115)"

# Stop local Prometheus + Grafana observability stack.
observability-down:
	@printf "$(ICON_STEP) %s\n" "Stopping observability stack..."
	@docker compose -f docker-compose.observability.yml down
	@printf "$(ICON_OK) %s\n" "Observability stack stopped"

# Smoke-check that key observability links are reachable locally.
observability-smoke:
	@printf "$(ICON_STEP) %s\n" "Checking observability links..."
	@$(PYTHON) scripts/check_observability_links.py
	@printf "$(ICON_OK) %s\n" "Observability links are reachable"

# ──────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────
# Validate local environment prerequisites and app config load.
env-check:
	@printf "$(ICON_STEP) %s\n" "Checking environment…"
	@if [ ! -d ".venv" ]; then printf "  $(ICON_ERR) %s\n" ".venv missing"; else printf "  $(ICON_OK) %s\n" ".venv exists"; fi
	@if [ ! -f "$(ENV)" ]; then printf "  $(ICON_ERR) %s\n" ".env missing"; else printf "  $(ICON_OK) %s\n" ".env exists"; fi
	@if [ ! -f "requirements.txt" ]; then printf "  $(ICON_ERR) %s\n" "requirements.txt missing"; else printf "  $(ICON_OK) %s\n" "requirements.txt exists"; fi
	@printf "  $(ICON_INFO) APP_ENV=%s\n" "$${APP_ENV:-<not set>}"
	@printf "  $(ICON_INFO) ENV_FILE=%s\n" "$${ENV_FILE:-<not set>}"
	@if [ -d ".venv" ] && [ -f "$(ENV)" ]; then \
		$(PYTHON) -c "from app.core.config import get_settings; s=get_settings(); print('  $(ICON_OK) Config OK - DB:', s.sqlite_db_path)" 2>/dev/null \
		|| printf "  $(ICON_ERR) %s\n" "Config load failed (check .env values)"; \
	fi
	@printf "$(ICON_STEP) %s\n" "Done"
