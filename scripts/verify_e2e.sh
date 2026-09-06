#!/usr/bin/env bash
# Phase 3.6 — boot backend + frontend, then run Playwright e2e specs.
#
# Usage:
#   bash scripts/verify_e2e.sh [PLAYWRIGHT_PORT]
#
# Defaults to 18006 for the frontend, 18800 for the backend (kept off the
# project's "live" ports so this never collides with a manual demo run).

set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
FRONTEND="$ROOT/frontend"
BACKEND_PORT=${BACKEND_PORT:-18800}
FRONTEND_PORT=${1:-${PLAYWRIGHT_PORT:-18006}}
LOG_DIR="$ROOT/.claude/logs/$(date -u +%Y-%m-%d)"
mkdir -p "$LOG_DIR"

cleanup() {
  set +e
  if [[ -n "${BACKEND_PID-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null
  fi
  if [[ -n "${VITE_PID-}" ]] && kill -0 "$VITE_PID" 2>/dev/null; then
    kill "$VITE_PID" 2>/dev/null
  fi
  set -e
}
trap cleanup EXIT

echo "=== verify_e2e: backend on $BACKEND_PORT, frontend on $FRONTEND_PORT ==="

# Reuse if backend is already alive on the target port.
if curl -sSf "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1; then
  echo "[backend] reusing existing instance"
else
  (
    cd "$ROOT"
    nohup uvicorn backend.api.main:app \
      --host 127.0.0.1 --port "$BACKEND_PORT" \
      --log-level warning > "$LOG_DIR/e2e-backend.log" 2>&1 &
    echo $! > /tmp/e2e-backend.pid
  )
  BACKEND_PID=$(cat /tmp/e2e-backend.pid)
  for _ in {1..20}; do
    if curl -sSf "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
  curl -sSf "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null
  echo "[backend] up (pid=$BACKEND_PID)"
fi

# Frontend: build + preview gives a deterministic, HMR-free server that
# is friendlier to headless browser automation than `vite dev`.
if curl -sSf "http://127.0.0.1:$FRONTEND_PORT/" >/dev/null 2>&1; then
  echo "[frontend] reusing existing server on $FRONTEND_PORT"
else
  echo "[frontend] building..."
  (
    cd "$FRONTEND"
    VITE_API_BASE="http://127.0.0.1:$BACKEND_PORT" \
      npm run build > "$LOG_DIR/e2e-frontend-build.log" 2>&1
  )
  (
    cd "$FRONTEND"
    nohup npx vite preview --port "$FRONTEND_PORT" --strictPort --host 127.0.0.1 \
      > "$LOG_DIR/e2e-frontend-preview.log" 2>&1 &
    echo $! > /tmp/e2e-frontend.pid
  )
  VITE_PID=$(cat /tmp/e2e-frontend.pid)
  for _ in {1..30}; do
    if curl -sSf "http://127.0.0.1:$FRONTEND_PORT/" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
  curl -sSf "http://127.0.0.1:$FRONTEND_PORT/" >/dev/null
  echo "[frontend] preview up on $FRONTEND_PORT (pid=$VITE_PID)"
fi

echo "=== running playwright ==="
cd "$FRONTEND"
PLAYWRIGHT_PORT="$FRONTEND_PORT" npx playwright test --reporter=list \
  | tee "$LOG_DIR/e2e-playwright.log"
