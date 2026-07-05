# Agent Service

The Agent Service is the internal Python reasoning layer for Chip Orchestra. It keeps the existing FastAPI + LangGraph service pattern, but upgrades the single templated executor into **stage-specialized handlers** that produce real, evidence-backed workspace artifacts.

It is **internal** — the public `orchestrator-service` is the only authenticated gateway.

## Agent roles & stage handlers
Stages are dispatched to dedicated handlers (`agents/stage_handlers.py`); the LangGraph shape (`load_memory → select_agent → execute_agent → persist_feedback`) is preserved.

| Stage | Agent | Output |
| --- | --- | --- |
| `SPEC_INGEST` | SpecInterpreter | `spec/design_brief.md`, `spec/spec.json` |
| `PLAN` | FlowAssistant | `plans/execution_plan.md` |
| `RTL_GEN` | RTLAuthor | `rtl/<top>.sv`, `reports/rtl_architecture.md` |
| `TB_GEN` | Verifier | `tb/<top>_tb.sv` (self-checking, VCD dump) |
| `SIGNOFF` | FlowAssistant | `reports/signoff_summary.md` (from EDA metrics) |
| `EXPORT` | FlowAssistant | `reports/final_design_report.md`, `architecture_overview.md`, `runbook.md` |
| _other_ (`SIM`/`LINT`/`SYNTH`/`PNR`/`DRC_LVS`/…) | Diagnoser/Verifier/FlowAssistant | `reports/<stage>_notes.md` fallback |

### Evidence-backed reporting
`reporting/evidence.py` scans the shared task workspace (RTL, testbenches, waveforms, GDS) and parses EDA `reports/<stage>_report.json` files into a `ReportContext`; `reporting/markdown_report.py` renders the final report, architecture overview and runbook from that evidence rather than hallucinating.

### Workspace helpers & tools
`context/files.py` provides safe workspace I/O (rejects absolute paths and `..`). The tool registry (`tools/registry.py`) exposes real workspace tools — `list_workspace_files`, `read_workspace_file`, `write_workspace_file`, `read_stage_report`, `write_stage_summary`, `record_task_note`, `record_artifact_metadata`. `submit_eda_job` / `get_eda_result` remain callable placeholders but EDA submission is owned by the orchestrator.

## Endpoint
- `POST /agent/invoke` — receives `prompt`, `tools`, `context`, and optional `workspace_root`, `artifact_inventory`, `eda_reports`, `reference_files`; returns structured outputs plus optional `structured_conclusion` and `artifact_refs`
- `GET /health` — readiness check

## Environment variables
| Var | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | — | Memory store (MySQL) |
| `REDIS_URL` | — | Diagnosis cache / progress |
| `AGENT_ARTIFACT_ROOT` | falls back to `WORKSPACE_ROOT` then `/tmp/chip-orchestra/workspaces` | Workspace root |
| `LLM_PROVIDER` | `mock` | Reasoning provider (deterministic mock by default) |
| `MODEL_NAME` | `mock-deterministic` | Model name for the provider |
| `MAX_CONTEXT_TOKENS` | `8192` | Context budget |
| `DEFAULT_USERNAME` / `DEFAULT_FULL_NAME` | — | User context defaults |

## Local run
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

## Tests
```bash
pytest -q
```
