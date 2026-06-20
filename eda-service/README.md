# EDA Service

The EDA Service is the execution-plane runtime for Chip Orchestra. It keeps the lightweight FastAPI implementation style from the old backend, but adapts it into a dedicated job service with MySQL persistence, Redis queueing, SSE log streaming, and stubbed hooks for OpenLane, Verilator, Yosys, KLayout, and Magic.

## Endpoints
- `POST /eda/jobs`
- `GET /eda/jobs/{id}/status`
- `GET /eda/jobs/{id}/report`
- `GET /eda/jobs/{id}/logs`
- `DELETE /eda/jobs/{id}`
- `GET /health`

## Local run
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8002
```
