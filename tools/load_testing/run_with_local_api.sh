#!/usr/bin/env bash
# Start API with a high rate limit, wait for /ready, run tools.load_testing.runner, stop API.
# Invoked from Makefile: make run-loadtest-api
#
# Optional variables:
#   API_RATE_LIMIT_REQUESTS_LOADTEST (default 1000000000), API_RATE_LIMIT_WINDOW_SECONDS_LOADTEST — API limits
#   LOADTEST_TOTAL_REQUESTS — request count (else LOADTEST_DEFAULT_* from .env and env/$APP_ENV, else 100)
#   LOADTEST_DELAY_MS — delay (ms); defaults from LOADTEST_DEFAULT_* in env/example and env/dev
# Load order: .env then env/$APP_ENV (same as app.core.config). Exports before make override files.
#   LOADTEST_RUNNER_EXTRA — extra runner args (quoted), e.g. "--seed 42"
#   LOADTEST_SKIP_CONFIRM=1 — skip confirmation prompt (CI / scripts)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

ENV_FILE="${ENV_FILE:-.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "${ENV_FILE} not found. Run: make env-init" >&2
  exit 1
fi
if [[ ! -f .venv/bin/python ]]; then
  echo ".venv/bin/python missing. Run: make venv && make install" >&2
  exit 1
fi

# Explicit export before make overrides values from files
# (with set -e, `[[ condition ]] && cmd` fails the script if condition is false)
_restore_loadtest_overrides() {
  if [[ "$_lt_preserve_total" -eq 1 ]]; then
    LOADTEST_TOTAL_REQUESTS="$_lt_save_total"
  fi
  if [[ "$_lt_preserve_delay" -eq 1 ]]; then
    LOADTEST_DELAY_MS="$_lt_save_delay"
  fi
  if [[ "$_lt_preserve_def_total" -eq 1 ]]; then
    LOADTEST_DEFAULT_TOTAL_REQUESTS="$_lt_save_def_total"
  fi
  if [[ "$_lt_preserve_def_delay" -eq 1 ]]; then
    LOADTEST_DEFAULT_DELAY_MS="$_lt_save_def_delay"
  fi
}
_lt_preserve_total=0
_lt_preserve_delay=0
_lt_preserve_def_total=0
_lt_preserve_def_delay=0
if [[ -n "${LOADTEST_TOTAL_REQUESTS+x}" ]]; then
  _lt_preserve_total=1
  _lt_save_total="$LOADTEST_TOTAL_REQUESTS"
fi
if [[ -n "${LOADTEST_DELAY_MS+x}" ]]; then
  _lt_preserve_delay=1
  _lt_save_delay="$LOADTEST_DELAY_MS"
fi
if [[ -n "${LOADTEST_DEFAULT_TOTAL_REQUESTS+x}" ]]; then
  _lt_preserve_def_total=1
  _lt_save_def_total="$LOADTEST_DEFAULT_TOTAL_REQUESTS"
fi
if [[ -n "${LOADTEST_DEFAULT_DELAY_MS+x}" ]]; then
  _lt_preserve_def_delay=1
  _lt_save_def_delay="$LOADTEST_DEFAULT_DELAY_MS"
fi

set -a
# shellcheck disable=SC1091
source "./$ENV_FILE"
APP_ENV="${APP_ENV:-dev}"
PROFILE="$ROOT/env/$APP_ENV"
if [[ -f "$PROFILE" ]]; then
  # shellcheck disable=SC1091
  source "$PROFILE"
fi
set +a

_restore_loadtest_overrides

export API_RATE_LIMIT_REQUESTS="${API_RATE_LIMIT_REQUESTS_LOADTEST:-1000000000}"
export API_RATE_LIMIT_WINDOW_SECONDS="${API_RATE_LIMIT_WINDOW_SECONDS_LOADTEST:-60}"

HOST="${APP_HOST:-127.0.0.1}"
PORT="${APP_PORT:-8000}"
CURL_HOST="$HOST"
if [[ "$HOST" == "0.0.0.0" ]]; then
  CURL_HOST="127.0.0.1"
fi

print_warning_and_confirm() {
  echo ""
  echo "Notice: run-loadtest-api will:"
  echo "  • start a separate uvicorn process (high rate limit, no --reload) at http://${CURL_HOST}:${PORT};"
  echo "  • after /ready responds, run python -m tools.load_testing.runner;"
  echo "  • when the runner finishes, stop that API process (temporary server)."
  echo ""
  echo "If an API is already running on this port (make run, make run-loadtest-api-serve, etc.),"
  echo "free port ${PORT} manually — otherwise the new instance cannot bind (address in use)."
  echo ""
  if [[ "${LOADTEST_SKIP_CONFIRM:-}" == "1" ]]; then
    echo "LOADTEST_SKIP_CONFIRM=1 — skipping confirmation."
    return 0
  fi
  local ans
  if [[ -c /dev/tty ]]; then
    read -r -p "Continue? [y/n]: " ans < /dev/tty || true
  elif [[ -t 0 ]]; then
    read -r -p "Continue? [y/n]: " ans || true
  else
    echo "No TTY for yes/no — skipping confirmation (set LOADTEST_SKIP_CONFIRM=1 explicitly in CI)."
    return 0
  fi
  case "$ans" in
    y|Y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

if ! print_warning_and_confirm; then
  echo "Cancelled."
  exit 0
fi

echo "→ Starting uvicorn (loadtest limits: ${API_RATE_LIMIT_REQUESTS}/${API_RATE_LIMIT_WINDOW_SECONDS}s)…"
.venv/bin/python -m uvicorn app.main:app --host "$HOST" --port "$PORT" &
UV_PID=$!

cleanup() {
  if kill -0 "$UV_PID" 2>/dev/null; then
    echo "→ Stopping API (pid $UV_PID)…"
    kill "$UV_PID" 2>/dev/null || true
    wait "$UV_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "→ Waiting for http://${CURL_HOST}:${PORT}/ready …"
READY_OK=0
for _ in $(seq 1 60); do
  if curl -sf "http://${CURL_HOST}:${PORT}/ready" >/dev/null; then
    READY_OK=1
    break
  fi
  sleep 1
done
if [[ "$READY_OK" -ne 1 ]]; then
  echo "✗ API did not become ready in time." >&2
  exit 1
fi

export LOAD_TEST_BASE_URL="http://${CURL_HOST}:${PORT}"
: "${LOADTEST_DEFAULT_TOTAL_REQUESTS:=100}"
: "${LOADTEST_DEFAULT_DELAY_MS:=0}"
TOTAL="${LOADTEST_TOTAL_REQUESTS:-$LOADTEST_DEFAULT_TOTAL_REQUESTS}"
DELAY="${LOADTEST_DELAY_MS:-$LOADTEST_DEFAULT_DELAY_MS}"

echo "→ Running: python -m tools.load_testing.runner --total-requests ${TOTAL} --delay-ms ${DELAY} ${LOADTEST_RUNNER_EXTRA:-}"
# shellcheck disable=SC2086
set +e
.venv/bin/python -m tools.load_testing.runner --total-requests "$TOTAL" --delay-ms "$DELAY" ${LOADTEST_RUNNER_EXTRA:-}
RC=$?
set -e
exit "$RC"
