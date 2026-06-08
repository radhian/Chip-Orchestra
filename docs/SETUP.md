# Chip Orchestra — Setup & Running

End-to-end instructions to run the agentic platform (backend + frontend).

## Prerequisites

| Tool        | Why                            | Check                  |
|-------------|--------------------------------|------------------------|
| `uv`        | Python env + deps for backend  | `uv --version`         |
| Node ≥ 18   | Frontend build/dev             | `node --version`       |
| `npm` ≥ 11  | Frontend deps                  | `npm --version`        |
| Ollama      | Local LLM (`qwen3.5:9b`)       | `ollama list`          |
| `iverilog`  | RTL simulation                 | `iverilog -V`          |
| LibreLane   | RTL→GDSII hardening (optional) | `librelane --version`  |
| Docker      | Postgres + MinIO (optional)    | `docker ps`            |

> On this dev machine `uv`, Node 20, Ollama (`qwen3.5:9b`), `iverilog 11.0`, and
> `nix` are already installed.

## One command (recommended)

```bash
./run.sh            # installs deps on first run, then starts both servers
./run.sh --setup    # force-reinstall backend + frontend dependencies
```

- Frontend → http://localhost:5173
- Backend  → http://localhost:8000  (API docs at `/docs`)

`Ctrl+C` stops both. The script also warns if Ollama isn't reachable.

## Manual (two terminals)

**Backend**

```bash
cd backend
uv venv --python 3.12
uv pip install -e .
cp .env.example .env
uv run uvicorn chip_orchestra_backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend**

```bash
cd frontend
npm install
npm run dev          # or: node_modules/.bin/vite --host
```

Create `frontend/.env` (run.sh does this automatically):

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCKS=true
```

## Using it

1. Open http://localhost:5173 → **Create Design Task**.
2. Type a natural-language **design brief** (e.g. a UART transmitter), pick a
   **PDK** (Sky130 or GF180), set the target clock and review gates, choose a
   **Research depth** on the slider (Small 3+3 · Medium 6+6 · Deep 10+10 GitHub+web
   reference sources), and **Launch agentic task**.
3. You land on **Task Detail & Runbook**, which polls live as the agent plans,
   generates RTL, simulates, self-corrects, and (if LibreLane is configured)
   hardens to GDSII. Watch:
   - **Runbook** — the live agent transcript + AI diagnosis
   - **RTL Workspace** — the generated `.v` / `.sv` / `.sdc` files
   - **Signoff & Delivery** — the checklist + export bundle

> With `OLLAMA_THINK=true` and `qwen3.5:9b`, expect **minutes per step** and a
> long total runtime — this is intentional for RTL quality. The UI streams
> progress the whole time.

## Persistence (free + local)

Chip runs auto-save their **logs, files, and state**. Two storage backends, both
**free and 100% local** — nothing is cloud/paid:

- **PostgreSQL** (local Docker container) — task state + the runbook log.
- **MinIO** (local Docker container) — generated files (RTL/TB/sim/GDS/bundles).
  MinIO is a self-hosted, free, S3-API-compatible server on your own disk; it is
  **not AWS S3** and incurs no cost.

`./run.sh` starts both via `docker compose up -d`; data lives in local Docker
volumes (`pgdata`, `miniodata`). A fresh clone starts **empty** and fills as you
generate chips. MinIO console: http://localhost:9001 (user `chip` / `chipsecret`).

**Zero-infra mode (no Docker, no DB):** comment out `DATABASE_URL` and the `S3_*`
lines in `backend/.env` (or run `NO_DOCKER=1 ./run.sh`). Everything then saves to
the local file store under `backend/.workspaces/` — also free and local.

## Enabling LibreLane (GDSII)

Without LibreLane the flow still generates and verifies RTL, and the
Implementation stage reports "pending — install LibreLane". To produce a real
GDSII, set in `backend/.env`:

```env
RUN_HARDEN=true
LIBRELANE_CMD=nix run github:librelane/librelane --
```

(or `LIBRELANE_CMD=librelane` if it's on your PATH).

## Troubleshooting

- **`npm install` fails ("Exit handler never called!" or `bnpm.byted.org` ENOTFOUND)** —
  resolved. It was npm 10.8's crash bug plus a `package-lock.json` pinned to an
  internal mirror. Fixed by `npm install -g npm@latest` and regenerating the
  lockfile against the public registry (`rm package-lock.json node_modules && npm install`).
  pnpm 10 (`--ignore-workspace`) also works as a fallback.
- **"failed to initialize model: qwen3next: layer 32 missing"** — the
  `gds-qwen35-4b` model is corrupted in Ollama; re-pull it or stick with
  `qwen3.5:9b` (the configured default).
- **Generated RTL is empty / file is `dut.v`** — the model's response was
  truncated because Ollama's context window was too small for the `<think>`
  block + code. Raise `OLLAMA_NUM_CTX` (default 32768) in `backend/.env`. The
  agent also retries once with reasoning disabled as a safety net.
- **RTL generation hangs / errors** — ensure `ollama serve` is running and
  `qwen3.5:9b` is pulled (`ollama list`).
- **Overview is empty** — expected with a fresh backend; create a task. The
  hardcoded sidebar demo link (`/tasks/fft-1024p`) falls back to mock data.
- **Reset state** — stop the backend and delete `backend/.workspaces/`.
