#!/usr/bin/env bash
set -euo pipefail

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP for ACME redirect'
ufw allow 443/tcp comment 'HTTPS for public API'
ufw allow from 10.0.0.20 to any port 3306 proto tcp comment 'EDA VM to MySQL'
ufw allow from 10.0.0.20 to any port 6379 proto tcp comment 'EDA VM to Redis'
ufw enable
ufw status verbose
