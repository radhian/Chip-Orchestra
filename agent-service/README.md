# Agent Service

The Agent Service is the Python reasoning layer for Chip Orchestra. It keeps the existing FastAPI service pattern from the old repo, but upgrades it into a deterministic LangGraph-based deep-agent runtime with reusable tools, MySQL-backed memory, and Redis diagnosis caching.

## Agent roles
- SpecInterpreter
- RTLAuthor
- Verifier
- Diagnoser
- FlowAssistant

## Endpoint
- `POST /agent/invoke` — receive prompt + tool manifest from the Orchestrator Service and return structured outputs
- `GET /health` — readiness check

## Environment variables
- `DATABASE_URL`
- `REDIS_URL`
- `DEFAULT_USERNAME`
- `DEFAULT_FULL_NAME`

## Local run
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```
