#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

printf '\n==> Running Orchestrator Service tests\n'
(cd "$ROOT_DIR/orchestrator-service" && make test)

printf '\n==> Running agent-service tests\n'
(cd "$ROOT_DIR/agent-service" && make test)

printf '\n==> Running eda-service tests\n'
(cd "$ROOT_DIR/eda-service" && make test)

printf '\nAll backend test suites passed.\n'
