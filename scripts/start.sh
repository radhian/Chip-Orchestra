#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker compose up -d --build

echo "Chip Orchestra is starting..."
echo "Frontend:         http://localhost:${FRONTEND_PORT:-4173}"
echo "Orchestrator Service: http://localhost:${OPERATOR_PORT:-8080}"
echo "Agent Service:    http://localhost:${AGENT_PORT:-8001}"
echo "EDA Service:      http://localhost:${EDA_PORT:-8002}"
