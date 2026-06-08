# Chip Orchestra — System Architecture

This document describes Chip Orchestra **after** the agentic AI integration: how
the React frontend, the FastAPI backend, and the GarudaChip-derived agent core
fit together to turn a natural-language design brief into verified RTL and a
hardened GDSII layout.

---

## 1. What the system is now

Chip Orchestra is a **task-centric, browser-native digital chip design platform**.
Previously the frontend was a mockup backed only by local mock data. It is now
wired to a **real agentic backend** that runs an end-to-end RTL→GDSII flow:

```
Design brief (plain English)
        │
        ▼
  Agent plan ─► Research (crawl4ai + RAG) ─► Generate RTL ─► Decompose ─► Testbench ─► Simulate (iverilog)
        ▲                                                      │
        └──────────  self-correct (fix RTL / fix TB)  ◄────────┘ (fail, retry)
                                                               │ (pass)
                                                               ▼
                                          Harden with LibreLane (RTL→GDSII)
                                                               │
                                                               ▼
                                              Signoff package + export bundle
```

Every step is **observable**: it streams into the same task object the frontend
already renders — stages, runbook events, artifacts, AI diagnosis, workspace
files, and the signoff checklist.

The agent core is adapted from **[GarudaChip](https://github.com/adeirman46/GarudaChip)**
(LangGraph + local Ollama). Rather than reusing GarudaChip's Streamlit UI, the
agent was re-targeted to implement **Chip Orchestra's existing REST contract**,
so the platform's existing screens drive a real pipeline.

---

## 2. High-level architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Browser (React + Vite + Tailwind + shadcn/ui)        frontend/           │
│                                                                          │
│  Overview Console ──► Create Design Task ──► Task Detail & Runbook        │
│       (list)              (NL brief form)      (Runbook / RTL / Signoff)  │
│                                                                          │
│  src/api/tasks.ts  ── typed fetch + mock fallback (VITE_API_BASE_URL) ──┐ │
└──────────────────────────────────────────────────────────────────────┼─┘
                              REST / JSON (camelCase)                    │
┌──────────────────────────────────────────────────────────────────────▼─┐
│  FastAPI backend                                       backend/          │
│                                                                          │
│  main.py        14-route Chip Orchestra API (== src/api/tasks.ts)        │
│  runner.py      task lifecycle + ThreadPool background execution         │
│  store.py       in-memory tasks + file cache → Postgres + object storage │
│  persistence.py PostgreSQL (state + logs) + S3/MinIO (files), optional    │
│  models.py      Pydantic shapes == src/types/chiporchestra.ts            │
│  config.py      env / .env settings                                      │
│                                                                          │
│  agent/                                                                   │
│    graph.py     LangGraph state machine + Reporter (progress → store)    │
│    prompts.py   plan / generate / decompose / testbench / fix prompts    │
│    llm.py       Ollama (qwen3.5:9b) + response parsing                   │
│    eda.py       iverilog simulation + LibreLane hardening wrappers       │
└──────────────────────────────────────────────────────────────────────┬─┘
                                                                         │
                ┌──────────────────────────┬─────────────────────────────┘
                ▼                          ▼                            ▼
          Ollama (LLM)            Icarus Verilog (sim)          LibreLane (GDS)
       qwen3.5:9b, local          iverilog / vvp              nix-installed, opt.

         Durable backing (config-driven, optional):
           PostgreSQL  ── task state + runbook log (tasks / events / files tables)
           S3 / MinIO  ── generated files (RTL / TB / sim / GDS / bundles)
```

---

## 3. The agent pipeline (LangGraph)

`backend/chip_orchestra_backend/agent/graph.py` compiles a `StateGraph` whose
nodes mirror GarudaChip's agent set. Each node reports progress through a
`Reporter` that writes into the task store.

| Node            | Does                                                        | LLM | Tool |
|-----------------|-------------------------------------------------------------|-----|------|
| `plan`          | Drafts a build plan from the brief                          | ✅  |      |
| `retrieve`      | Web search → crawl4ai → FAISS RAG of reference designs       |     | 🌐   |
| `generate`      | Produces synthesizable Verilog, grounded in retrieved refs  | ✅  |      |
| `decompose`     | Splits RTL into one file per module (deterministic, multi-file) |     |      |
| `testbench`     | Writes a self-checking TB (`Result: PASSED/FAILED`)         | ✅  |      |
| `simulate`      | Compiles + runs with iverilog/vvp, parses the result        |     | ✅   |
| `route_fix`     | Decides DESIGN vs TESTBENCH is at fault → emits diagnosis    | ✅  |      |
| `fix_design`    | Regenerates RTL (temperature scales with attempt #)         | ✅  |      |
| `fix_testbench` | Regenerates the testbench                                   | ✅  |      |
| `harden`        | Runs LibreLane RTL→GDSII, collects metrics                  |     | ✅   |
| `finalize`      | Builds the signoff checklist + final status                |     |      |

**Control flow** (cycles allowed, `recursion_limit=60`):

```
plan → generate → decompose → testbench → simulate
                                            │
        ┌───────────────────────────────────┼──────────────────────────┐
        │ pass                               │ fail & retries left      │ exhausted
        ▼                                    ▼                          ▼
      harden                            route_fix                 verify_failed
        │                              ╱        ╲                       │
        ▼                       fix_design   fix_testbench              │
     finalize ◄──────────────────────┴──────────┴── (back to simulate) │
        │                                                               │
        └──────────────────────────► END ◄──────────────────────────────┘
```

The **self-correction loop** (`MAX_RETRIES`, default 3) re-simulates after each
repair, exactly like GarudaChip — but the routing decision and each patch are
surfaced as runbook events and an AI-diagnosis card in the UI.

---

## 4. Stage mapping (GarudaChip → Chip Orchestra)

The agent's fine-grained steps roll up into Chip Orchestra's five canonical
stages (the keys the frontend renders):

| Chip Orchestra stage  | Agent steps that drive it                         |
|-----------------------|---------------------------------------------------|
| `spec-intake`         | Brief ingested, plan drafted                      |
| `agent-planning`      | RTL generated + decomposed                         |
| `verification-loop`   | Testbench, simulation, self-correction            |
| `implementation`      | LibreLane hardening (synth / P&R / signoff)       |
| `delivery`            | Signoff package + one-click export bundle         |

---

## 5. Request / data flow

1. **Create** — `POST /api/tasks` with `{ task: { name, design_brief, pdk_id, … } }`.
   `runner.create_task` builds the initial `TaskDetail` (5 stages), stores it,
   and submits the LangGraph pipeline to a background `ThreadPoolExecutor`. The
   response returns immediately so the UI can navigate to the task.
2. **Run** — the pipeline executes node-by-node, each calling `Reporter` →
   `TaskStore` to append events, flip stage status, register artifacts/files,
   set diagnosis, and finally the signoff status. Every mutation persists a
   `task.json` snapshot.
3. **Observe** — the frontend **polls** every 4 s (task detail) / 5 s (overview)
   via the existing `src/api/tasks.ts` calls, so the runbook, RTL workspace,
   artifacts, and signoff fill in live.
4. **Interact** — engineers can `propose-patch` (agent applies an instruction to
   the RTL), `approve/reject` a stage, file a `waiver`, `retry`, or
   `export-bundle` (zips the workspace).

---

## 6. API contract

The backend implements exactly the calls in `frontend/src/api/tasks.ts`, with
the camelCase response shapes from `frontend/src/types/chiporchestra.ts`.

```
GET    /api/tasks                                  list (filters: owner, status, stage, repo, needs_review, failed)
POST   /api/tasks                                  create + launch pipeline
GET    /api/tasks/{id}                             task detail
GET    /api/tasks/{id}/stages                      stage timeline
POST   /api/tasks/{id}/retry                       re-run from spec intake
POST   /api/tasks/{id}/stop                         pause at the next step boundary (resumable)
POST   /api/tasks/{id}/resume                       resume a paused run from its checkpoint
POST   /api/tasks/{id}/cancel                       cancel a running/paused run
GET    /api/tasks/{id}/attempts/latest/events      runbook (live agent transcript)
GET    /api/tasks/{id}/attempts/latest/artifacts   generated files index
GET    /api/tasks/{id}/attempts/latest/diagnosis   AI diagnosis cards
GET    /api/tasks/{id}/workspace/files             RTL/TB/SDC summaries
GET    /api/tasks/{id}/workspace/file?path=…       file contents (RTL Workspace)
POST   /api/tasks/{id}/workspace/propose-patch     agent edits RTL from an instruction
GET    /api/tasks/{id}/signoff/status              signoff checklist
POST   /api/tasks/{id}/approvals/{stage}           approve / reject a gate
POST   /api/tasks/{id}/waivers                     file a waiver
POST   /api/tasks/{id}/export-bundle               zip the handoff bundle
GET    /health                                     liveness + active model
```

Interactive docs: **http://localhost:8000/docs** (FastAPI/Swagger).

---

## 7. Workspace layout

Each task gets a directory under `WORKSPACE_ROOT` (default `backend/.workspaces/`):

```
backend/.workspaces/<task-id>/
├── task.json              # persisted task snapshot (restart-durable)
├── docs/plan.md           # agent build plan
├── rtl/<module>.v[h]      # generated / patched RTL
├── tb/<top>_tb.v          # self-checking testbench
├── sim/simulation.log     # iverilog + vvp output, *.vcd waveform
├── harden/                # LibreLane config.json, log, runs, metrics.json, *.gds
└── bundles/<id>.zip       # exported handoff bundles
```

---

## 8. Configuration

All via `backend/.env` (see `backend/.env.example`). Highlights:

| Variable          | Default            | Purpose                                       |
|-------------------|--------------------|-----------------------------------------------|
| `OLLAMA_MODEL`    | `qwen3.5:9b`       | Local LLM used by every agent step            |
| `OLLAMA_THINK`    | `true`             | Qwen3 deep reasoning (slow, high quality)     |
| `OLLAMA_NUM_CTX`  | `32768`            | Context window — must be large or thinking truncates the code |
| `LLM_PROVIDER`    | `ollama`           | `ollama` or `gemini` (needs the `gemini` extra)|
| `USE_WEB`         | `true`             | crawl4ai web research for reference designs   |
| `USE_RAG`         | `true`             | sentence-transformers + FAISS retrieval       |
| `MAX_RETRIES`     | `3`                | Self-correction iterations                    |
| `RUN_HARDEN`      | `true`             | Attempt LibreLane RTL→GDSII                    |
| `LIBRELANE_CMD`   | `librelane`        | How to invoke LibreLane (e.g. `nix run …`)     |
| `WORKSPACE_ROOT`  | `./.workspaces`    | Local working cache for tasks + files         |
| `DATABASE_URL`    | (set)              | Postgres for durable state + logs (unset = off)|
| `S3_ENDPOINT_URL` | (set)              | S3/MinIO for durable file storage (unset = off)|

---

## 9. Design decisions & notes

- **Follows the frontend, not GarudaChip's UI.** The integration re-implements
  Chip Orchestra's API and maps the agent onto its task model, rather than
  embedding GarudaChip's Streamlit app — per the "follow the frontend need" goal.
- **qwen3.5:9b with thinking ON** is the configured model. It is deliberately
  slow (minutes per step; a full RTL→GDS task can take well over an hour) in
  exchange for higher-quality RTL. `OLLAMA_THINK=false` trades quality for speed.
- **LibreLane is best-effort.** If `LIBRELANE_CMD` isn't installed, verification
  still runs and the implementation stage reports "pending — install LibreLane"
  with a diagnosis, instead of crashing. Enable GDS with e.g.
  `LIBRELANE_CMD="nix run github:librelane/librelane --"`.
- **Grounded generation (RAG + web).** `USE_WEB`/`USE_RAG` are ON by default: the
  `retrieve` node searches the web, crawls reference HDL with **crawl4ai**, embeds
  the results with **sentence-transformers**, indexes them in **FAISS**, and injects
  the top matches into the generator (see `agent/research.py`). It degrades
  gracefully — no network or missing deps just means generation proceeds on model
  knowledge. Requires `uv pip install -e '.[research]'` + `playwright install chromium`.
- **Persistence is free, local, and optional.** Postgres + MinIO run as local
  Docker containers (MinIO is self-hosted S3-compatible storage, **not** AWS — no
  cloud cost). A clone boots empty and auto-fills; data lives in local Docker
  volumes. Unset `DATABASE_URL`/`S3_*` to run on the local file store with no infra.
- **No placeholder data.** The frontend ships with `VITE_USE_MOCKS=false` and no
  seed tasks — the Overview is empty until you create a real task.
- **Cooperative run control.** Stop/Cancel are checked both at node boundaries
  and **between streamed LLM tokens** (`control.py`), so a long qwen3.5:9b step is
  interrupted within ~a token rather than running to completion. A LangGraph
  `MemorySaver` checkpoint lets a paused run **resume** where it left off; resume
  falls back to a fresh run if the checkpoint is gone (server restart).
- **Robust LLM parsing.** `llm.py` strips `<think>` reasoning and tolerates
  unclosed/missing code fences (a real bug found and fixed during integration).

---

## 10. Extension points

- Enable **RAG**: install the `rag` extra and point `RAG_INDEX_DIR` at a FAISS
  Verilog corpus; wire it into `node_generate`'s `reference` slot.
- Swap models per task: the create payload accepts an optional `model` field.
- Replace polling with WebSocket/SSE streaming for sub-second runbook updates.
- Add persistence beyond `task.json` (a DB) for multi-user history.
