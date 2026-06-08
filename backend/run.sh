#!/usr/bin/env bash
# Start the Chip Orchestra agentic backend.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created backend/.env from .env.example"
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

exec uv run uvicorn chip_orchestra_backend.main:app --host "$HOST" --port "$PORT" "$@"
