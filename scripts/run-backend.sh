#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../backend"

echo "Starting Restate server..."
restate-server &
RESTATE_PID=$!

# Give Restate a moment to start
sleep 2

echo "Starting backend..."
uv run uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

cleanup() {
  echo "Shutting down..."
  kill $BACKEND_PID 2>/dev/null || true
  kill $RESTATE_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait
