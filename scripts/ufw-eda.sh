#!/usr/bin/env bash
set -euo pipefail

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow from 10.0.0.10 to any port 8002 proto tcp comment 'Core VM to EDA API'
ufw enable
ufw status verbose
