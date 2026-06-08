# Chip Orchestra Backend

An agentic **RTL-to-GDSII** backend for the Chip Orchestra frontend. The agent
core is adapted from [GarudaChip](https://github.com/adeirman46/GarudaChip)
(LangGraph + local Ollama → Verilog → Icarus simulation → LibreLane hardening),
but instead of GarudaChip's Streamlit UI it implements **the exact REST contract
the Chip Orchestra frontend already expects** and maps the agent's progress onto
Chip Orchestra's task model.

## What it does

`POST /api/tasks` with a natural-language **design brief** launches a background
LangGraph pipeline:

```
plan → research (crawl4ai + RAG) → generate RTL → decompose → testbench → simulate (iverilog)
        ↘ self-correct (route → fix RTL / fix TB → re-simulate) ↗
                                   → harden (LibreLane → GDSII) → signoff
```

Every node streams into the same task object the frontend reads:

| Agent step                | Chip Orchestra surface |
|---------------------------|------------------------|
| plan / spec ingest        | Stage **Spec intake**, runbook event, `docs/plan.md` |
| generate + decompose RTL  | Stage **Agent planning**, `rtl/*.v` in RTL Workspace |
| testbench + simulate      | Stage **Verification loop**, `sim/simulation.log`, waveform artifact |
| self-correction loop      | Runbook events + **AI diagnosis** (DESIGN vs TESTBENCH) |
| LibreLane harden          | Stage **Implementation**, GDS + metrics artifacts |
| signoff                   | Stage **Delivery**, signoff checklist + export bundle |

## Tech stack

- **API**: FastAPI + Uvicorn
- **Agent**: LangGraph, `langchain-ollama` (default model `qwen3.5:9b`)
- **Verification**: Icarus Verilog (`iverilog` / `vvp`)
- **Implementation**: LibreLane (RTL→GDSII), best-effort
- **Package manager**: `uv`

## Setup

```bash
cd backend
uv venv --python 3.12
uv pip install -e .
cp .env.example .env       # adjust model / tooling if needed
```

Optional extras:

```bash
uv pip install -e '.[gemini]'    # Google Gemini fallback provider
uv pip install -e '.[research]'  # crawl4ai web research + FAISS RAG (grounded agent)
python -m playwright install chromium   # browser used by crawl4ai
```

**Grounded generation (RAG + web).** With the `research` extra installed, the agent's
`retrieve` node searches the web, crawls reference HDL with crawl4ai, embeds the results
(sentence-transformers), indexes them with FAISS, and injects the most relevant snippets
into the generator. It's ON by default (`USE_WEB`/`USE_RAG=true`) and degrades gracefully
if the deps/browser/network are unavailable.

Prerequisites already present on the dev machine: Ollama (with `qwen3.5:9b`),
`iverilog 11.0`, `nix`. LibreLane can be enabled by setting `LIBRELANE_CMD`
in `.env` (e.g. `nix run github:librelane/librelane --`); without it the flow
still generates and verifies RTL and reports that implementation is pending.

## Run

```bash
./run.sh                   # or:
uv run uvicorn chip_orchestra_backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Health check: `curl http://localhost:8000/health`.

## API surface

Mirrors `frontend/src/api/tasks.ts` exactly:

```
GET    /api/tasks                                   POST /api/tasks
GET    /api/tasks/{id}                              GET  /api/tasks/{id}/stages
POST   /api/tasks/{id}/retry
POST   /api/tasks/{id}/stop  /resume  /cancel       pause / resume / cancel a run
GET    /api/tasks/{id}/attempts/latest/events
GET    /api/tasks/{id}/attempts/latest/artifacts
GET    /api/tasks/{id}/attempts/latest/diagnosis
GET    /api/tasks/{id}/workspace/files              GET  /api/tasks/{id}/workspace/file?path=
POST   /api/tasks/{id}/workspace/propose-patch
GET    /api/tasks/{id}/signoff/status
POST   /api/tasks/{id}/approvals/{stage}            POST /api/tasks/{id}/waivers
POST   /api/tasks/{id}/export-bundle
```

Generated task workspaces (RTL/TB/sim/harden + `task.json`) live under
`WORKSPACE_ROOT` (default `backend/.workspaces/`).

## Persistence (PostgreSQL + object storage)

Config-driven and optional. When `DATABASE_URL` is set, task **state + the runbook
log** are mirrored to **PostgreSQL**; when S3 creds are set, every generated file
(RTL/TB/sim/GDS/bundles) is mirrored to **S3/MinIO object storage**. With neither
set, the backend runs on the local file store (`.workspaces/`) only.

- A fresh clone **boots empty** (no committed data) and **auto-fills** as you
  generate chips — nothing is hand-seeded.
- Schema (`tasks`, `events`, `files`) and the bucket are created automatically.
- On restart the store **hydrates from Postgres**; a local cache miss for a file
  is **pulled back from object storage**.
- All persistence calls are defensive — if Postgres/MinIO is unreachable the agent
  keeps running and just uses the file store.

Local infra via Docker (matches `.env.example`):

```bash
docker compose up -d        # from repo root — Postgres :5432, MinIO :9000 (console :9001)
```

Point `DATABASE_URL` / `S3_*` at managed/cloud Postgres + S3 instead to deploy
elsewhere. `run.sh` brings the Docker infra up automatically (skip with `NO_DOCKER=1`).

## Configuration

See [.env.example](.env.example). Key knobs: `OLLAMA_MODEL`, `OLLAMA_NUM_CTX`,
`USE_WEB`/`USE_RAG`, `MAX_RETRIES`, `RUN_HARDEN`, `LIBRELANE_CMD`, `WORKSPACE_ROOT`,
`DATABASE_URL`, `S3_ENDPOINT_URL`.
