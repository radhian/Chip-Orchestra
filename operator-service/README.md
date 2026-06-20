# Orchestrator Service

The Orchestrator Service is the Go-based control plane for Chip Orchestra. It combines REST APIs, WebSocket fan-out, DAG scheduling, stage retries, JWT authentication, Redis-backed task events, and service-to-service dispatching for the Agent Service and EDA Service.

## Highlights
- Gin-based HTTP API and task event WebSocket
- GORM models for `users`, `tasks`, `stages`, and `stage_attempts`
- MySQL for durable workflow metadata
- Redis for artifact cache, workspace snapshots, events, and pub/sub
- Background DAG scheduler that advances stages as dependencies complete
- HS256 JWT login for MVP usage

## Environment variables
- `PORT` — HTTP port, default `8080`
- `MYSQL_DSN` — MySQL DSN
- `REDIS_ADDR` — Redis address, default `redis:6379`
- `JWT_SECRET` — HS256 signing secret
- `AGENT_SERVICE_URL` — Agent Service base URL
- `EDA_SERVICE_URL` — EDA Service base URL
- `DEFAULT_USERNAME` / `DEFAULT_FULL_NAME` / `DEFAULT_EMAIL` / `DEFAULT_PASSWORD` — seeded local login

## Main endpoints
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/tasks`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/:id`
- `PATCH /api/v1/tasks/:id`
- `GET /api/v1/tasks/:id/stages`
- `POST /api/v1/tasks/:id/stages/:stage/retry`
- `GET /api/v1/tasks/:id/attempts/latest/events`
- `GET /ws/tasks/:id/events`

## Local run
```bash
go mod tidy
go run ./cmd/operator
```

Use the seeded login credentials from `.env` to get a JWT for the frontend or WebSocket client.
