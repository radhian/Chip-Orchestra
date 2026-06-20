#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Missing dependency: docker"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Missing dependency: docker compose"
  exit 1
fi

for cmd in go python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing dependency: $cmd"
    exit 1
  fi
done

if [ ! -f "$ROOT_DIR/.env" ]; then
  if [ ! -f "$ROOT_DIR/.env.example" ]; then
    echo "ERROR: .env.example not found at $ROOT_DIR/.env.example"
    echo "Please make sure you are running this script from inside the chip-orchestra/ directory."
    exit 1
  fi
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  echo "Created .env from .env.example"
fi

docker compose pull mysql redis || true

echo "Setup complete. Review .env if you want to customize ports or credentials."
