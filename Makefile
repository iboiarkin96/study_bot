PYTHON := .venv/bin/python
PIP    := .venv/bin/pip
ENV    := .env
DEPLOY_CMD ?=
COLOR_RESET := \033[0m
COLOR_GREEN := \033[32m
COLOR_RED   := \033[31m
COLOR_CYAN  := \033[36m
ICON_OK   := $(COLOR_GREEN)✓$(COLOR_RESET)
ICON_ERR  := $(COLOR_RED)✗$(COLOR_RESET)
ICON_STEP := $(COLOR_CYAN)→$(COLOR_RESET)

.PHONY: help venv install requirements run migrate migration docs docs-watch docs-check test test-one pre-deploy deploy check sync-docs

# ──────────────────────────────────────────────
# Help
# ──────────────────────────────────────────────
help:
	@echo ""
	@echo "  Study App — available commands"
	@echo "  ─────────────────────────────────────────"
	@echo "  make venv             Create virtual environment"
	@echo "  make install          Install dependencies"
	@echo "  make requirements     Auto-generate requirements.txt from .venv"
	@echo "  make run              Start FastAPI dev server"
	@echo "  make migrate          Apply all Alembic migrations"
	@echo "  make migration name=… Auto-generate new Alembic migration"
	@echo "  make docs             Regenerate UML docs once"
	@echo "  make docs-watch       Watch UML sources, regenerate on change"
	@echo "  make docs-check       Verify generated docs are up to date"
	@echo "  make test             Run full test suite (pytest)"
	@echo "  make test-one path=…  Run one test file or node"
	@echo "  make pre-deploy       Run full quality gate before deploy"
	@echo "  make deploy DEPLOY_CMD='…'  Run pre-deploy then deploy command"
	@echo "  make check            Verify env, deps, and DB connectivity"
	@echo "  make sync-docs        Auto-update README.md & docs/index.html from code"
	@echo ""

# ──────────────────────────────────────────────
# Environment
# ──────────────────────────────────────────────
venv:
	@if [ -d ".venv" ]; then \
		printf "$(ICON_OK) %s\n" ".venv already exists"; \
	else \
		printf "$(ICON_STEP) %s\n" "Creating virtual environment…"; \
		python3 -m venv .venv && printf "$(ICON_OK) %s\n" ".venv created"; \
	fi

install:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Upgrading pip…"
	@$(PYTHON) -m pip install --upgrade pip -q
	@printf "$(ICON_STEP) %s\n" "Installing requirements…"
	@$(PIP) install -r requirements.txt -q
	@printf "$(ICON_OK) %s\n" "Dependencies installed"

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
migrate:
	@if [ ! -f "$(ENV)" ]; then \
		printf "$(ICON_ERR) %s\n" "$(ENV) not found. Cannot resolve SQLITE_DB_PATH."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Applying migrations…"
	@$(PYTHON) -m alembic upgrade head && printf "$(ICON_OK) %s\n" "Migrations applied"

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
docs:
	@if [ ! -f "scripts/regenerate_docs.py" ]; then \
		printf "$(ICON_ERR) %s\n" "scripts/regenerate_docs.py not found."; exit 1; \
	fi
	@$(PYTHON) scripts/regenerate_docs.py

docs-watch:
	@if [ ! -f "scripts/regenerate_docs.py" ]; then \
		printf "$(ICON_ERR) %s\n" "scripts/regenerate_docs.py not found."; exit 1; \
	fi
	@$(PYTHON) scripts/regenerate_docs.py --watch

docs-check:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Checking generated UML artifacts..."
	@$(PYTHON) scripts/regenerate_docs.py --check
	@printf "$(ICON_STEP) %s\n" "Checking synced documentation sections..."
	@$(PYTHON) scripts/sync_docs.py --check
	@printf "$(ICON_OK) %s\n" "Docs-as-Code checks passed"

# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────
test:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Running tests…"
	@$(PYTHON) -m pytest -q

test-one:
	@if [ -z "$(path)" ]; then \
		echo ""; \
		printf "$(ICON_ERR) %s\n" "Missing test path."; \
		echo ""; \
		echo "  Usage:"; \
		echo "    make test-one path=tests/api/v1/test_users_register.py"; \
		echo ""; \
		exit 1; \
	fi
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Running selected tests: $(path)"
	@$(PYTHON) -m pytest -q $(path)

pre-deploy:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Pre-deploy pipeline started"
	@$(MAKE) check
	@$(MAKE) test
	@$(MAKE) docs
	@$(MAKE) sync-docs
	@$(MAKE) docs-check
	@printf "$(ICON_OK) %s\n" "Pre-deploy pipeline passed (checks, tests, docs, sync-docs, docs-check)"

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
	@printf "$(ICON_STEP) %s\n" "Deploy pipeline started"
	@$(MAKE) pre-deploy
	@printf "$(ICON_STEP) %s\n" "Running deploy command: $(DEPLOY_CMD)"
	@sh -c "$(DEPLOY_CMD)"
	@printf "$(ICON_OK) %s\n" "Deploy pipeline finished"

# ──────────────────────────────────────────────
# Sync docs from code
# ──────────────────────────────────────────────
sync-docs:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@$(PYTHON) scripts/sync_docs.py

# ──────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────
check:
	@printf "$(ICON_STEP) %s\n" "Checking environment…"
	@if [ ! -d ".venv" ]; then printf "  $(ICON_ERR) %s\n" ".venv missing"; else printf "  $(ICON_OK) %s\n" ".venv exists"; fi
	@if [ ! -f "$(ENV)" ]; then printf "  $(ICON_ERR) %s\n" ".env missing"; else printf "  $(ICON_OK) %s\n" ".env exists"; fi
	@if [ ! -f "requirements.txt" ]; then printf "  $(ICON_ERR) %s\n" "requirements.txt missing"; else printf "  $(ICON_OK) %s\n" "requirements.txt exists"; fi
	@if [ -d ".venv" ] && [ -f "$(ENV)" ]; then \
		$(PYTHON) -c "from app.core.config import get_settings; s=get_settings(); print('  $(ICON_OK) Config OK - DB:', s.sqlite_db_path)" 2>/dev/null \
		|| printf "  $(ICON_ERR) %s\n" "Config load failed (check .env values)"; \
	fi
	@printf "$(ICON_STEP) %s\n" "Done"
