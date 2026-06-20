# Chip Orchestra Frontend

This React + TypeScript + Vite application is the browser UI for Chip Orchestra. It now consumes live Orchestrator Service REST and WebSocket APIs only—mock task data has been removed.

## Highlights
- React 18 + TypeScript + Vite
- Tailwind CSS and shadcn/ui components
- JWT-based login screen backed by `POST /api/v1/auth/login`
- Overview, task creation, runbook, RTL workspace, and signoff screens powered by live API data
- Live task event streaming through `ws://host/ws/tasks/:id/events`

## Environment variables
- `VITE_API_BASE_URL` — Orchestrator Service base URL, default `http://localhost:8080`
- `VITE_AUTH_STORAGE_KEY` — localStorage key used to persist the JWT session, default `chip-orchestra.auth`

## Local run
```bash
npm install
cp .env.example .env
npm run dev
```

Open the app, sign in with an Orchestrator Service username/password, and the frontend will store the JWT in localStorage for subsequent REST and WebSocket calls.

## Routes
- `/overview`
- `/tasks/new`
- `/tasks/:id`
- `/tasks/:id/rtl`
- `/tasks/:id/signoff`

## Live API usage
The frontend talks to the Orchestrator Service under `/api/v1/*` and `ws://.../ws/tasks/:id/events`, including:
- `POST /api/v1/auth/login` for JWT login
- `GET /api/v1/tasks` for overview list loading
- `POST /api/v1/tasks` for task creation
- `GET /api/v1/tasks/:id` for task detail
- `GET /api/v1/tasks/:id/stages` for timeline and retry state
- `POST /api/v1/tasks/:id/stages/:stage/retry` for stage retries
- `GET /api/v1/tasks/:id/attempts/latest/events` plus WebSocket events for the runbook log
- `GET /api/v1/tasks/:id/workspace/files` and `GET /api/v1/tasks/:id/workspace/file` for RTL workspace browsing
- `GET /api/v1/tasks/:id/signoff/status` and `POST /api/v1/tasks/:id/approvals/:stage` for signoff

## Build verification
Use the standard Vite build:
```bash
npm run build
```
