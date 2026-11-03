#!/usr/bin/env bash
set -euo pipefail

LAN_CIDR="${LAN_CIDR:-172.16.100.0/24}"
EDA_HOST="${EDA_HOST:-10.0.0.20}"
PODMAN_CIDR="${PODMAN_CIDR:-10.90.0.0/24}"
OPERATOR_PORT="${OPERATOR_PORT:-8080}"
FRONTEND_PORT="${FRONTEND_PORT:-4173}"

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP for ACME redirect'
ufw allow 443/tcp comment 'HTTPS for public API'
ufw allow from "$LAN_CIDR" to any port "$OPERATOR_PORT" proto tcp comment 'Chip Orchestra API from LAN'
ufw allow from "$LAN_CIDR" to any port "$FRONTEND_PORT" proto tcp comment 'Chip Orchestra frontend from LAN'
ufw allow from "$EDA_HOST" to any port 3306 proto tcp comment 'EDA VM to MySQL'
ufw allow from "$EDA_HOST" to any port 6379 proto tcp comment 'EDA VM to Redis'
ufw allow from "$PODMAN_CIDR" to any port 3306 proto tcp comment 'Rootless Podman to MySQL'
ufw allow from "$PODMAN_CIDR" to any port 6379 proto tcp comment 'Rootless Podman to Redis'
ufw enable
ufw status verbose
