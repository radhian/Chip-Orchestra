# Development Guide

## Prerequisites
- Docker and Docker Compose
- Go 1.23+
- Python 3.12+
- Node.js 18+

## First-time setup
```bash
cp .env.example .env
bash scripts/setup.sh
```

## Local service development
### Orchestrator Service
```bash
cd orchestrator-service
go mod tidy
go run ./cmd/orchestrator
```

### Agent Service
```bash
cd agent-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

### EDA Service
```bash
cd eda-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8002
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## Container workflows
- `bash scripts/start.sh` — start the full stack
- `bash scripts/stop.sh` — stop the full stack
- `bash scripts/migrate.sh` — run MySQL schema migration through the Orchestrator Service

## Notes
- The frontend automatically logs in with the seeded local credentials from `.env`.
- Orchestrator Service performs GORM migrations automatically on startup.
- Redis stores task events, workspace file snapshots, diagnosis cache, and EDA job logs.
