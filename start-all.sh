#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

API_HOST="${HERALD_API_HOST:-127.0.0.1}"
API_PORT="${HERALD_API_PORT:-8000}"
WEB_UI_DIR="${HERALD_WEB_UI_DIR:-$ROOT_DIR/web-ui}"
WEB_UI_PORT="${HERALD_WEB_UI_PORT:-4321}"

echo "Starting FastAPI API on http://${API_HOST}:${API_PORT}..."
(
  cd "$ROOT_DIR"
  uvicorn src.web.api:app --reload --host "$API_HOST" --port "$API_PORT"
) &
API_PID=$!

echo "Starting Web UI in $WEB_UI_DIR..."
(
  cd "$WEB_UI_DIR"
  HERALD_API_TARGET="http://${API_HOST}:${API_PORT}" HERALD_WEB_UI_PORT="$WEB_UI_PORT" npm run dev
) &
WEB_UI_PID=$!

cleanup() {
  echo "Stopping processes..."
  kill "$API_PID" "$WEB_UI_PID" 2>/dev/null || true
}

trap cleanup INT TERM

while true; do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "API process exited."
    break
  fi
  if ! kill -0 "$WEB_UI_PID" 2>/dev/null; then
    echo "Web UI process exited."
    break
  fi
  sleep 1
done

cleanup
wait || true

