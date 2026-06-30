#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker compose up -d mysql redis
sleep 5
docker compose run --rm -e MIGRATE_ONLY=true orchestrator-service

echo "MySQL migrations completed through the Orchestrator Service."
