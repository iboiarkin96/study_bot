PYTHON := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: help venv install run migrate migration docs docs-watch

help:
	@echo "Available commands:"
	@echo "  make venv        - create virtual environment"
	@echo "  make install     - install dependencies from requirements.txt"
	@echo "  make run         - run FastAPI service"
	@echo "  make migrate     - apply Alembic migrations"
	@echo "  make migration   - create new Alembic migration (name=...)"
	@echo "  make docs        - regenerate UML docs once"
	@echo "  make docs-watch  - watch UML sources and regenerate docs automatically"

venv:
	if [ ! -d ".venv" ]; then python3 -m venv .venv; else echo ".venv already exists"; fi

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PIP) install -r requirements.txt

run:
	set -a; . ./.env; set +a; $(PYTHON) -m uvicorn app.main:app --host $$APP_HOST --port $$APP_PORT --reload

migrate:
	$(PYTHON) -m alembic upgrade head

migration:
	@if [ -z "$(name)" ]; then echo "Usage: make migration name=create_xxx"; exit 1; fi
	$(PYTHON) -m alembic revision --autogenerate -m "$(name)"

docs:
	$(PYTHON) docs/regenerate_docs.py

docs-watch:
	$(PYTHON) docs/regenerate_docs.py --watch
