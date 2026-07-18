# Agent Service

The Agent Service is the internal Python reasoning layer for Chip Orchestra. It keeps the existing FastAPI + LangGraph service pattern, but upgrades the single templated executor into **stage-specialized handlers** that produce real, evidence-backed workspace artifacts.

It is **internal** — the public `orchestrator-service` is the only authenticated gateway.

## Agent roles & stage handlers
Stages are dispatched to dedicated handlers (`agents/stage_handlers.py`); the LangGraph shape (`load_memory → select_agent → execute_agent → persist_feedback`) is preserved (`agents/graph.py`).

| Stage | Agent | Output |
| --- | --- | --- |
| `SPEC_INGEST` | SpecInterpreter | `spec/design_brief.md`, `spec/spec.json`, `context/uploads_digest.md` (image/PDF digest) |
| `PLAN` | FlowAssistant | `plans/execution_plan.md`, `context/design_notes.md`, `context/sources.md` |
| `RTL_GEN` | RTLAuthor | `rtl/<top>.sv`, submodule `rtl/*.v`, `rtl/*.mem`, `reports/rtl_architecture.md` |
| `RTL_REPAIR` | RTLAuthor | compile-/golden-fixed `rtl/` files, `reports/rtl_repair.md` |
| `TB_GEN` | Verifier | `tb/<top>_tb.sv` (self-checking, VCD dump), `context/chip_input_grid.json`, `waves/golden_output.mem` |
| `SIM` | Verifier | diagnosis notes; SIM execution itself is owned by the EDA/orchestrator plane |
| `SIGNOFF` | FlowAssistant | `reports/signoff_summary.md` (from EDA metrics) |
| `EXPORT` | FlowAssistant | `reports/final_design_report.md`, `reports/architecture_overview.md`, `reports/runbook.md`, `exports/final_report.tex`, `final_report.pdf` |
| _other_ (`LINT`/`SYNTH`/`PNR`/`DRC_LVS`/…) | Diagnoser | `reports/<stage>_notes.md` fallback |

### Deep-agent
When `AGENT_DEEP_AGENTS=1` (default) and a real LLM provider is configured, `PLAN` / `RTL_GEN` / `RTL_REPAIR` / `TB_GEN` run as a **recursive language-model deep agent** (`agents/deep_agent.py`) that treats the workspace as an environment rather than a single prompt:

- **Sliced reasoning** — `read_file_disk`, `grep_files`, `llm_query`, and `task` for focused sub-queries over large files.
- **Compile-check-on-write** — `write_file_disk` runs `iverilog -tnull` and enters a fix-on-error loop (bounded by `MAX_REPAIR_ITERS`).
- **Data-driven design** — a `run_python` sandbox generates golden `.mem` vectors or trains weights (numpy/torch), installing packages into `AGENT_PYDEPS_DIR`.
- **Autonomous research** — `search_web` and `fetch_reference` (`research.py`) pull external references (GitHub via `GITHUB_TOKEN`).
- **Memory & lessons** — `recall_memory` reuses prior error→fix patterns (`lessons.py`, `knowledge/error_fixes.json`).
- **Vision digest** — attached images/PDFs are parsed to `context/uploads_digest.md` (`uploads.py`, `extract.py`).

Set `AGENT_DEEP_AGENTS=0` to fall back to one-shot templated stage handlers.

### Evidence-backed reporting
`reporting/evidence.py` scans the shared task workspace (RTL, testbenches, waveforms, GDS) and parses EDA `reports/<stage>_report.json` files into a `ReportContext`; `reporting/markdown_report.py` renders the final report, architecture overview and runbook from that evidence rather than hallucinating.

### Workspace helpers & tools
`context/files.py` provides safe workspace I/O (rejects absolute paths and `..`). The tool registry (`tools/registry.py`) exposes real workspace and task tools — `list_workspace_files`, `read_workspace_file`, `write_workspace_file`, `read_stage_report`, `write_stage_summary`, `record_task_note`, `record_artifact_metadata`, `read_artifact`, `write_artifact`, `update_task_status`, `track_task_progress`, `get_user_context`. `submit_eda_job` / `get_eda_result` remain callable placeholders but EDA submission is owned by the orchestrator.

## Endpoints
- `POST /agent/invoke` — receives `prompt`, `stage`, `tools`, `context`, and optional `workspace_root`, `artifact_inventory`, `eda_reports`, `reference_files`, `attachments`; returns structured outputs plus optional `structured_conclusion` and `artifact_refs`
- `GET /agent/models` — lists the active provider, default model, available models, and vision capability flags
- `GET /health` — readiness check (includes Redis connectivity)

## Environment variables
| Var | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | — | Memory store (MySQL) |
| `REDIS_URL` | `redis://redis:6379/0` | Diagnosis cache / progress |
| `AGENT_ARTIFACT_ROOT` | falls back to `WORKSPACE_ROOT` then `/tmp/chip-orchestra/workspaces` | Workspace root |
| `LLM_PROVIDER` | `mock` | Reasoning provider: `ollama`, `google` (Gemini), `openai`, `glm` (ZhipuAI), or `mock` |
| `OLLAMA_MODEL` | `glm-5.2:cloud` | Default model (Ollama provider) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `AGENT_DEEP_AGENTS` | `1` | Enable the RLM deep agent (`0` = templated fallback) |
| `AGENT_PYDEPS_DIR` | workspace-relative | Install dir for `run_python` packages |
| `MAX_REPAIR_ITERS` | `3` | Compile/golden fix-on-error rounds inside a handler |
| `GARUDA_VISION` / `GARUDA_VISION_MODEL` | auto-detect | Vision support override / vision model for `describe_image` |
| `GITHUB_TOKEN` | — | Auth for `fetch_reference` against GitHub |
| `MAX_CONTEXT_TOKENS` | `8192` | Context budget |
| `DEFAULT_USERNAME` / `DEFAULT_FULL_NAME` | — | User context defaults |

## LLM providers
`llm.py` supports **Ollama** (local or cloud models such as `glm-5.2:cloud`, Qwen, Mistral), **Google Gemini**, **OpenAI**, **ZhipuAI GLM**, and a deterministic **mock** provider (default). Vision requests route to a local VLM when the active model is text-only, or natively to Gemini.

## Local run
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

## Tests
```bash
pytest -q
```
