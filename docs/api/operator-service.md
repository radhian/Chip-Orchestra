# Orchestrator Service API

## Authentication
### `POST /api/v1/auth/login`
Request:
```json
{
  "username": "radhian.armansyah",
  "password": "chip-orchestra"
}
```
Response contains an HS256 bearer token.

### `GET /api/v1/auth/me`
Returns the current principal extracted from JWT claims.

## Tasks
### `POST /api/v1/tasks`
Creates a task, initializes the default stage DAG, and queues `SPEC_INGEST`.

### `GET /api/v1/tasks`
Lists tasks with optional filters such as `status` and `stage`.

### `GET /api/v1/tasks/{id}`
Returns task detail formatted for the frontend task pages.

### `PATCH /api/v1/tasks/{id}`
Updates editable task fields such as description or current stage.

## Stages
### `GET /api/v1/tasks/{id}/stages`
Returns all stage nodes with dependency and retry metadata.

### `POST /api/v1/tasks/{id}/stages/{stage}/retry`
Resets the requested stage and downstream dependent stages, then re-schedules the DAG.

## Runbook and workspace
- `GET /api/v1/tasks/{id}/attempts/latest/events`
- `GET /api/v1/tasks/{id}/attempts/latest/artifacts`
- `GET /api/v1/tasks/{id}/attempts/latest/diagnosis`
- `GET /api/v1/tasks/{id}/workspace/files`
- `GET /api/v1/tasks/{id}/workspace/file?path=...`
- `POST /api/v1/tasks/{id}/workspace/propose-patch`
- `GET /api/v1/tasks/{id}/signoff/status`
- `POST /api/v1/tasks/{id}/approvals/{stage}`
- `POST /api/v1/tasks/{id}/waivers`
- `POST /api/v1/tasks/{id}/export-bundle`

## WebSocket
### `GET /ws/tasks/{id}/events?token=<jwt>`
Subscribes to Redis pub/sub task events for live frontend updates.
