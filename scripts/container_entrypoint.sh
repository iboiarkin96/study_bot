#!/usr/bin/env sh
# Shared process bootstrap: Alembic migrations, then Uvicorn.
# Used by the Docker image (WORKDIR /app) and optionally via `make container-start` on the host.
# Intentionally does not invoke Makefile: the image has no venv/.env; Make targets assume dev layout.
set -e
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

export SQLITE_DB_PATH="${SQLITE_DB_PATH:-/data/study_app.db}"
export LOG_DIR="${LOG_DIR:-/tmp/logs}"
mkdir -p "$(dirname "$SQLITE_DB_PATH")" 2>/dev/null || true
mkdir -p "$LOG_DIR" 2>/dev/null || true

PYTHON_CMD="${PYTHON:-python3}"
"$PYTHON_CMD" -m alembic upgrade head
exec "$PYTHON_CMD" -m uvicorn app.main:app --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8000}"
