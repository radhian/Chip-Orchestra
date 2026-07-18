# Orchestrator Service

The Orchestrator Service is the Go-based control plane for Chip Orchestra. It combines REST APIs, WebSocket fan-out, DAG scheduling, stage retries, budgeted auto-repair, JWT authentication, Redis-backed task events, workspace file serving, and service-to-service dispatching for the Agent Service and EDA Service.

## Highlights
- Gin-based HTTP API and task event WebSocket
- GORM models for `users`, `tasks`, `stages`, and `stage_attempts`
- MySQL for durable workflow metadata
- Redis for artifact cache, workspace snapshots, events, and pub/sub
- Background DAG scheduler that advances stages as dependencies complete (poll loop every ~3s)
- Budgeted auto-repair loops that dispatch the `RTL_REPAIR` deep agent on SIM / hardening failures
- Workspace file browsing, text/binary serving, and one-click `.zip` export
- Signoff status, human approval gates, and waivers for `FULL_FLOW_GATED` tasks
- HS256 JWT login (24h expiry), with `?token=<jwt>` query auth for browser downloads and WebSocket

## Pipeline

The scheduler drives a **15-stage** DAG (defined in `internal/orchestrator/orchestrator.go`):

```text
SPEC_INGEST → PLAN → RTL_GEN → TB_GEN → SIM → LINT → RTL_REPAIR → SYNTH*
  → PNR → { STA, GL_SIM, RENDER, DRC_LVS } → SIGNOFF* → EXPORT
```

- `SIM` depends on both `RTL_GEN` and `TB_GEN`; `RTL_REPAIR` depends on `SIM` and `LINT`.
- `STA`, `GL_SIM`, `RENDER`, and `DRC_LVS` fan out from `PNR` and reconverge at `SIGNOFF`.
- Stages marked `*` (`SYNTH`, `SIGNOFF`) are `Gated` human-review checkpoints in `FULL_FLOW_GATED` launch mode.
- Each stage has a `Kind` (`agent` or `eda`): `agent` stages dispatch to the Agent Service `/agent/invoke`; `eda` stages dispatch to the EDA Service `/eda/jobs`.

### Auto-repair

- On a SIM failure, the scheduler dispatches the `RTL_REPAIR` agent with the failure evidence, bounded by `SIM_AUTO_REPAIR_ROUNDS` (default `10`), tracked in Redis (`task:<id>:sim_auto_repairs`).
- On a PNR / DRC_LVS "no GDS" failure, it dispatches `RTL_REPAIR` bounded by `HARDEN_AUTO_REPAIR_ROUNDS` (default `3`), tracked in `task:<id>:harden_auto_repairs`.
- A manual stage `retry` resets the target stage and all its transitive dependents to `NOT_STARTED` and re-arms the budgets.

## Environment variables
- `PORT` — HTTP port, default `8080`
- `MYSQL_DSN` — MySQL DSN, default `chip:chip@tcp(mysql:3306)/chip_orchestra?...`
- `REDIS_ADDR` — Redis address, default `redis:6379`
- `JWT_SECRET` — HS256 signing secret
- `AGENT_SERVICE_URL` — Agent Service base URL, default `http://agent-service:8001`
- `EDA_SERVICE_URL` — EDA Service base URL, default `http://eda-service:8002`
- `WORKSPACE_ROOT` — shared workspace disk path, default `/tmp/chip-orchestra/workspaces`
- `SIM_AUTO_REPAIR_ROUNDS` — SIM auto-repair budget, default `10`
- `HARDEN_AUTO_REPAIR_ROUNDS` — hardening auto-repair budget, default `3`
- `GF180_VOLTAGE` — GF180MCU corner label passed through to the EDA Service (`3v3` default / `5v0`)
- `MIGRATE_ONLY` — when `true`, run DB migrations and exit
- `DEFAULT_USERNAME` / `DEFAULT_FULL_NAME` / `DEFAULT_EMAIL` / `DEFAULT_PASSWORD` — seeded local login

## Main endpoints

### Auth
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/llm/models` (proxies the Agent Service model list)

### Tasks & stages
- `POST /api/v1/tasks`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/:id`
- `PATCH /api/v1/tasks/:id`
- `DELETE /api/v1/tasks/:id`
- `GET /api/v1/tasks/:id/stages`
- `POST /api/v1/tasks/:id/stages/:stage/retry`

### Attempts, events & workspace
- `GET /api/v1/tasks/:id/attempts/latest/events`
- `GET /api/v1/tasks/:id/attempts/latest/artifacts`
- `GET /api/v1/tasks/:id/attempts/latest/diagnosis`
- `GET /api/v1/tasks/:id/workspace/files`
- `GET /api/v1/tasks/:id/workspace/file?path=<file>`
- `GET /api/v1/tasks/:id/workspace/raw?path=<file>` (binary / JWT-in-query)
- `GET /api/v1/tasks/:id/workspace/export` (`.zip`)
- `POST /api/v1/tasks/:id/workspace/upload`
- `POST /api/v1/tasks/:id/workspace/propose-patch`

### Signoff & review
- `GET /api/v1/tasks/:id/signoff/status`
- `POST /api/v1/tasks/:id/approvals/:stage`
- `POST /api/v1/tasks/:id/waivers`
- `POST /api/v1/tasks/:id/export-bundle`

### System & realtime
- `GET /health`
- `GET /ws/tasks/:id/events` (WebSocket; supports `?token=<jwt>`)

## Local run
```bash
go mod tidy
go run ./cmd/orchestrator
```

Use the seeded login credentials from `.env` to get a JWT for the frontend or WebSocket client.
