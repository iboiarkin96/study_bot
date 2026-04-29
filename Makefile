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

.PHONY: help setup dev check ci docs ship venv install deps-audit env-init run migrate format-fix format-check lint-check lint-fix dead-code-check type-check openapi-check contract-test openapi-accept-changes fix verify release-check release pre-commit-install pre-commit-check test test-one env-check docs-fix docs-check docs-html-check docs-design-check docs-a11y-check docs-feedback-check docs-spec-check

# ──────────────────────────────────────────────
# Help
# ──────────────────────────────────────────────
help:
	@echo ""
	@echo "  Study App — available commands"
	@echo "  ------------------------------------------------"
	@echo ""
	@echo "  Common commands (recommended)"
	@echo "  make setup                  # first-time local setup (.venv + install deps + .env)"
	@echo "  make dev                    # run local API (migrate + uvicorn)"
	@echo "  make fix                    # auto-fix code + docs"
	@echo "  make check                  # fast checks (lint/types/openapi/contract/tests)"
	@echo "  make ci                     # strict full gate (same as make verify)"
	@echo "  make docs                   # regenerate docs artifacts"
	@echo "  make ship                   # full pre-release gate (same as make release-check)"
	@echo ""
	@echo "  Production commands"
	@echo "  make release-check        Run env-check + deps-audit + verify before deploy"
	@echo "  make release DEPLOY_CMD='…' Run release-check then deploy command"
	@echo ""
	@echo "  Core commands"
	@echo ""
	@echo "  # Environment"
	@echo "  make venv                 Create virtual environment"
	@echo "  make install              Install dependencies"
	@echo "  make env-init             Create .env from env/example (once per machine)"
	@echo ""
	@echo "  # Application"
	@echo "  make run                  Start FastAPI dev server"
	@echo ""
	@echo "  # Database / Migrations"
	@echo "  make migrate              Apply all Alembic migrations"
	@echo ""
	@echo "  # Code Formatting"
	@echo "  make format-fix           Auto-format Python code"
	@echo "  make format-check         Verify code formatting (no changes)"
	@echo ""
	@echo "  # Linting"
	@echo "  make lint-fix             Run Ruff with auto-fixes"
	@echo "  make lint-check           Run Ruff lint checks"
	@echo "  make dead-code-check      Run Vulture"
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
	@echo "  make check                Run lint-check + type-check + openapi-check + contract-test + test"
	@echo "  make verify               Run deps-audit + lint-check + type-check + openapi-check + contract-test + test + docs-check + docs-a11y-check"
	@echo ""
	@echo "  # Supply chain (ADR 0019)"
	@echo "  make deps-audit           Scan requirements.txt with pip-audit (OSV); fails on known CVEs"
	@echo ""
	@echo "  # Tests"
	@echo "  make test                 Run full test suite (pytest + coverage per pyproject.toml)"
	@echo "  make test-one path=…      Run one test file or node"
	@echo ""
	@echo "  # Documentation"
	@echo "  make docs-fix             Auto-update docs (UML + markers + md→html + HTML repair + format + maintainers + portal data JS + pdoc API + search index)"
	@echo "  make docs-html-check      Validate HTML consistency (fails if docs HTML needs repair)"
	@echo "  make docs-design-check    Baseline docs design consistency checks (page skeleton, cards, mounts)"
	@echo "  make docs-a11y-check      Baseline accessibility checks (headings, landmarks, contrast, keyboard)"
	@echo "  make docs-feedback-check  Smoke-check page-level feedback wiring for key docs pages"
	@echo "  make docs-check           Verify docs are already in sync (fails on drift)"
	@echo ""
	@echo "  # Pre-commit Hooks"
	@echo "  make pre-commit-install   Install git pre-commit hooks"
	@echo "  make pre-commit-check     Run all pre-commit hooks"
	@echo ""
	@echo "  # Deployment"
	@echo "  make release-check        Run env-check + deps-audit + verify before deploy"
	@echo "  make release DEPLOY_CMD='…' Run release-check then deploy command"
	@echo ""

setup: venv install
	@if [ ! -f ".env" ]; then \
		$(MAKE) env-init; \
	else \
		printf "$(ICON_OK) %s\n" ".env already exists"; \
	fi

dev: run
check:
	@printf "$(COLOR_CYAN)== CHECK: START ==$(COLOR_RESET)\n"
	@printf "$(ICON_INFO) %s\n" "[1/5] lint-check"
	@$(MAKE) lint-check
	@printf "$(ICON_INFO) %s\n" "[2/5] type-check"
	@$(MAKE) type-check
	@printf "$(ICON_INFO) %s\n" "[3/5] openapi-check"
	@$(MAKE) openapi-check
	@printf "$(ICON_INFO) %s\n" "[4/5] contract-test"
	@$(MAKE) contract-test
	@printf "$(ICON_INFO) %s\n" "[5/5] test"
	@$(MAKE) test
	@printf "$(COLOR_GREEN)== CHECK: SUCCESS ==$(COLOR_RESET)\n"

ci: verify
docs: docs-fix
ship: release-check

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

# OSV-backed vulnerability scan of pinned dependencies (ADR 0019). Uses a repo-local cache (see .gitignore).
deps-audit:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@mkdir -p .pip-audit-cache
	@printf "$(ICON_STEP) %s\n" "Running pip-audit against requirements.txt…"
	@$(PYTHON) -m pip_audit -r requirements.txt --desc on --cache-dir .pip-audit-cache
	@printf "$(ICON_OK) %s\n" "pip-audit: no known vulnerabilities reported"

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
	@printf "$(ICON_STEP) %s\n" "Applying migrations then starting server (reading $(ENV))…"
	@set -a; . ./$(ENV); set +a; \
	APP_HOST=$${APP_HOST:-127.0.0.1}; \
	APP_PORT=$${APP_PORT:-8000}; \
	$(PYTHON) -m alembic upgrade head && \
	$(PYTHON) -m uvicorn app.main:app --host "$$APP_HOST" --port "$$APP_PORT" --reload --no-access-log

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

# Unused code scan (Vulture). Advisory: triage before deleting; extend [tool.vulture] or use
# vulture --ignore-names if a finding is a false positive (e.g. dynamic registration).
dead-code-check:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(ICON_STEP) %s\n" "Running Vulture dead-code scan..."
	@$(PYTHON) -m vulture
	@printf "$(ICON_OK) %s\n" "Vulture scan passed (no findings at configured min confidence)"

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

# Run strict quality gate (deps, lint, types, openapi, contract, tests, docs drift + a11y).
verify:
	@printf "$(COLOR_CYAN)== VERIFY: START ==$(COLOR_RESET)\n"
	@printf "$(ICON_INFO) %s\n" "[1/8] deps-audit"
	@$(MAKE) deps-audit
	@printf "$(ICON_INFO) %s\n" "[2/8] lint-check"
	@$(MAKE) lint-check
	@printf "$(ICON_INFO) %s\n" "[3/8] type-check"
	@$(MAKE) type-check
	@printf "$(ICON_INFO) %s\n" "[4/8] openapi-check"
	@$(MAKE) openapi-check
	@printf "$(ICON_INFO) %s\n" "[5/8] contract-test"
	@$(MAKE) contract-test
	@printf "$(ICON_INFO) %s\n" "[6/8] test"
	@$(MAKE) test
	@printf "$(ICON_INFO) %s\n" "[7/8] docs-check"
	@$(MAKE) docs-check
	@printf "$(ICON_INFO) %s\n" "[8/8] docs-a11y-check"
	@$(MAKE) docs-a11y-check
	@printf "$(COLOR_GREEN)== VERIFY: SUCCESS ==$(COLOR_RESET)\n"

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

# Run mandatory release gate (env-check + verify).
release-check:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(COLOR_CYAN)== RELEASE-CHECK: START ==$(COLOR_RESET)\n"
	@printf "$(ICON_INFO) %s\n" "[1/3] env-check"
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
	@printf "$(ICON_INFO) %s\n" "[1/8] regenerate UML diagrams"
	@$(PYTHON) scripts/regenerate_docs.py
	@printf "$(ICON_INFO) %s\n" "[2/8] sync marker-based documentation"
	@$(PYTHON) scripts/sync_docs.py
	@printf "$(ICON_INFO) %s\n" "[3/8] render docs markdown to html companions"
	@$(PYTHON) scripts/render_docs_html.py
	@printf "$(ICON_INFO) %s\n" "[4/8] repair docs html structure"
	@$(PYTHON) scripts/repair_docs_html.py
	@printf "$(ICON_INFO) %s\n" "[5/8] normalize docs html template"
	@$(PYTHON) scripts/format_docs_html.py
	@printf "$(ICON_INFO) %s\n" "[6/9] ensure docs body maintainers"
	@$(PYTHON) scripts/ensure_docs_maintainers.py
	@printf "$(ICON_INFO) %s\n" "[7/9] collect docs maintainer pages index"
	@$(PYTHON) scripts/collect_docs_portal_data.py
	@printf "$(ICON_INFO) %s\n" "[8/9] Python API reference (pdoc)"
	@rm -rf docs/pdoc
	@PYTHONHASHSEED=0 $(PYTHON) -m pdoc app -o docs/pdoc
	@$(PYTHON) scripts/normalize_pdoc_output.py
	@printf "$(ICON_INFO) %s\n" "[9/9] build docs search index"
	@$(PYTHON) scripts/build_docs_search_index.py
	@printf "$(COLOR_GREEN)== DOCS-FIX: SUCCESS ==$(COLOR_RESET)\n"

# Validate docs HTML structure is already normalized (no writes).
docs-html-check:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(COLOR_CYAN)== DOCS-HTML-CHECK: START ==$(COLOR_RESET)\n"
	@$(PYTHON) scripts/validate_docs_html.py
	@printf "$(COLOR_GREEN)== DOCS-HTML-CHECK: SUCCESS ==$(COLOR_RESET)\n"

# Baseline docs design checks (page skeleton and card conventions).
docs-design-check:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(COLOR_CYAN)== DOCS-DESIGN-CHECK: START ==$(COLOR_RESET)\n"
	@$(PYTHON) scripts/validate_docs_design.py
	@printf "$(COLOR_GREEN)== DOCS-DESIGN-CHECK: SUCCESS ==$(COLOR_RESET)\n"

# Baseline a11y checks for docs HTML (headings, landmarks, contrast, keyboard).
docs-a11y-check:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(COLOR_CYAN)== DOCS-A11Y-CHECK: START ==$(COLOR_RESET)\n"
	@$(PYTHON) scripts/validate_docs_a11y.py
	@printf "$(COLOR_GREEN)== DOCS-A11Y-CHECK: SUCCESS ==$(COLOR_RESET)\n"

# Smoke-check feedback controls wiring on key pages.
docs-feedback-check:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(COLOR_CYAN)== DOCS-FEEDBACK-CHECK: START ==$(COLOR_RESET)\n"
	@$(PYTHON) scripts/validate_docs_feedback.py
	@printf "$(COLOR_GREEN)== DOCS-FEEDBACK-CHECK: SUCCESS ==$(COLOR_RESET)\n"

# Lint internal analyst-spec pages (structure + cross-doc consistency).
# spec_lint.py    — per-page structure (required sections, metadata, examples, page history).
# spec_consistency.py — operationId ↔ spec page; error code/key ↔ shared error catalog.
docs-spec-check:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@printf "$(COLOR_CYAN)== DOCS-SPEC-CHECK: START ==$(COLOR_RESET)\n"
	@$(PYTHON) scripts/spec_lint.py
	@$(PYTHON) scripts/spec_consistency.py
	@printf "$(COLOR_GREEN)== DOCS-SPEC-CHECK: SUCCESS ==$(COLOR_RESET)\n"

# Verify docs are already synchronized (no drift allowed).
# Compare the full working tree diff vs HEAD before and after docs-fix. If identical,
# docs-fix did not change any file—so committed generated artifacts match the pipeline.
# (Local edits in unrelated paths are preserved as long as docs-fix leaves the tree unchanged.)
docs-check:
	@if [ ! -d ".venv" ]; then \
		printf "$(ICON_ERR) %s\n" ".venv not found. Run 'make venv && make install' first."; exit 1; \
	fi
	@$(MAKE) docs-html-check
	@$(MAKE) docs-design-check
	@$(MAKE) docs-feedback-check
	@$(MAKE) docs-spec-check
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
