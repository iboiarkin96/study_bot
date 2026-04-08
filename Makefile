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

.PHONY: help venv install requirements run migrate migration format format-check lint-check lint-fix type-check quality-check pre-commit-install pre-commit-check test test-one test-warnings pre-deploy deploy env-check sync-docs docs-format

# ──────────────────────────────────────────────
# Help
# ──────────────────────────────────────────────
help:
	@echo ""
	@echo "  Study App — available commands"
	@echo "  ------------------------------------------------"
	@echo ""
	@echo "  Quick workflows"
	@echo "  make quality-check          # local quality gate"
	@echo "  make sync-docs              # single docs pipeline (render + sync)"
	@echo "  make pre-deploy             # release gate before deploy"
	@echo "  make deploy DEPLOY_CMD='…'  # run deploy after gate"
	@echo ""
	@echo "  # Environment"
	@echo "  make venv                 Create virtual environment"
	@echo "  make install              Install dependencies"
	@echo "  make requirements         Auto-generate requirements.txt from .venv"
	@echo ""
	@echo "  # Application"
	@echo "  make run                  Start FastAPI dev server"
	@echo ""
	@echo "  # Database / Migrations"
	@echo "  make migrate              Apply all Alembic migrations"
	@echo "  make migration name=…     Auto-generate new Alembic migration"
	@echo ""
	@echo "  # Code Formatting"
	@echo "  make format               Auto-format Python code"
	@echo "  make format-check         Verify code formatting (no changes)"
	@echo ""
	@echo "  # Linting"
	@echo "  make lint-check           Run Ruff lint checks"
	@echo "  make lint-fix             Run Ruff with auto-fixes"
	@echo ""
	@echo "  # Type Checking"
	@echo "  make type-check           Run mypy type checks"
	@echo ""
	@echo "  # Environment Health"
	@echo "  make env-check            Verify env, deps, and DB connectivity"
	@echo ""
	@echo "  # Quality Gates"
	@echo "  make quality-check        Run lint-check + type-check + test + sync-docs"
	@echo ""
	@echo "  # Tests"
	@echo "  make test                 Run full test suite (pytest)"
	@echo "  make test-one path=…      Run one test file or node"
	@echo "  make test-warnings        Run tests with full warning details"
	@echo ""
	@echo "  # Documentation"
	@echo "  make sync-docs            Auto-update README.md & docs/system-analysis.html from code"
	@echo "  make docs-format          Apply shared HTML template to docs/*.html"
	@echo ""
	@echo "  # Pre-commit Hooks"
	@echo "  make pre-commit-install   Install git pre-commit hooks"
	@echo "  make pre-commit-check     Run all pre-commit hooks"
	@echo ""
	@echo "  # Deployment"
	@echo "  make pre-deploy           Run full quality gate before deploy"
	@echo "  make deploy DEPLOY_CMD='…' Run pre-deploy then deploy command"
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

# ──────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────
# Start FastAPI app with values from .env.
run:
	@if [ ! -f "$(ENV)" ]; then \
		printf "$(ICON_ERR) %s\n" "$(ENV) not found. Copy .env.example → .env and configure it."; exit 1; \
	fi
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Starting server (reading $(ENV))…"
	@set -a; . ./$(ENV); set +a; \
	$(PYTHON) -m uvicorn app.main:app --host $$APP_HOST --port $$APP_PORT --reload

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
format:
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

# Run full local quality gate (lint, types, tests, docs sync).
quality-check:
	@printf "$(COLOR_CYAN)== QUALITY-CHECK: START ==$(COLOR_RESET)\n"
	@printf "$(ICON_INFO) %s\n" "[1/4] lint-check"
	@$(MAKE) lint-check
	@printf "$(ICON_INFO) %s\n" "[2/4] type-check"
	@$(MAKE) type-check
	@printf "$(ICON_INFO) %s\n" "[3/4] test"
	@$(MAKE) test
	@printf "$(ICON_INFO) %s\n" "[4/4] sync-docs"
	@$(MAKE) sync-docs
	@printf "$(COLOR_GREEN)== QUALITY-CHECK: SUCCESS ==$(COLOR_RESET)\n"

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

# Run mandatory pre-deploy gate (env-check + quality-check).
pre-deploy:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(COLOR_CYAN)== PRE-DEPLOY: START ==$(COLOR_RESET)\n"
	@printf "$(ICON_INFO) %s\n" "[1/2] env-check"
	@$(MAKE) env-check
	@printf "$(ICON_INFO) %s\n" "[2/2] quality-check"
	@$(MAKE) quality-check
	@printf "$(COLOR_GREEN)== PRE-DEPLOY: SUCCESS ==$(COLOR_RESET)\n"

# Run deploy command after successful pre-deploy gate.
deploy:
	@if [ -z "$(DEPLOY_CMD)" ]; then \
		echo ""; \
		printf "$(ICON_ERR) %s\n" "Missing DEPLOY_CMD."; \
		echo ""; \
		echo "  Usage:"; \
		echo "    make deploy DEPLOY_CMD='echo Deploying to staging'"; \
		echo ""; \
		exit 1; \
	fi
	@printf "$(COLOR_CYAN)== DEPLOY: START ==$(COLOR_RESET)\n"
	@$(MAKE) pre-deploy
	@printf "$(ICON_STEP) %s\n" "Running deploy command: $(DEPLOY_CMD)"
	@sh -c "$(DEPLOY_CMD)"
	@printf "$(COLOR_GREEN)== DEPLOY: SUCCESS ==$(COLOR_RESET)\n"

# ──────────────────────────────────────────────
# Sync docs from code
# ──────────────────────────────────────────────
# Single docs command: regenerate UML, sync markers, render HTML companions.
sync-docs:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@if [ ! -f "scripts/regenerate_docs.py" ]; then \
		printf "$(ICON_ERR) %s\n" "scripts/regenerate_docs.py not found."; exit 1; \
	fi
	@printf "$(COLOR_CYAN)== DOCS SYNC: START ==$(COLOR_RESET)\n"
	@printf "$(ICON_INFO) %s\n" "[1/3] regenerate UML diagrams"
	@$(PYTHON) scripts/regenerate_docs.py
	@printf "$(ICON_INFO) %s\n" "[2/3] sync marker-based documentation"
	@$(PYTHON) scripts/sync_docs.py
	@printf "$(ICON_INFO) %s\n" "[3/4] render docs markdown to html companions"
	@$(PYTHON) scripts/render_docs_html.py
	@printf "$(ICON_INFO) %s\n" "[4/4] normalize docs html template"
	@$(PYTHON) scripts/format_docs_html.py
	@printf "$(COLOR_GREEN)== DOCS SYNC: SUCCESS ==$(COLOR_RESET)\n"

# Apply shared CSS/nav/container template to all docs html pages.
docs-format:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Formatting docs HTML files..."
	@$(PYTHON) scripts/format_docs_html.py
	@printf "$(ICON_OK) %s\n" "Docs HTML formatting completed"

# ──────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────
# Validate local environment prerequisites and app config load.
env-check:
	@printf "$(ICON_STEP) %s\n" "Checking environment…"
	@if [ ! -d ".venv" ]; then printf "  $(ICON_ERR) %s\n" ".venv missing"; else printf "  $(ICON_OK) %s\n" ".venv exists"; fi
	@if [ ! -f "$(ENV)" ]; then printf "  $(ICON_ERR) %s\n" ".env missing"; else printf "  $(ICON_OK) %s\n" ".env exists"; fi
	@if [ ! -f "requirements.txt" ]; then printf "  $(ICON_ERR) %s\n" "requirements.txt missing"; else printf "  $(ICON_OK) %s\n" "requirements.txt exists"; fi
	@if [ -d ".venv" ] && [ -f "$(ENV)" ]; then \
		$(PYTHON) -c "from app.core.config import get_settings; s=get_settings(); print('  $(ICON_OK) Config OK - DB:', s.sqlite_db_path)" 2>/dev/null \
		|| printf "  $(ICON_ERR) %s\n" "Config load failed (check .env values)"; \
	fi
	@printf "$(ICON_STEP) %s\n" "Done"
