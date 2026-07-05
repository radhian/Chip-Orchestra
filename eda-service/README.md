# EDA Service

The EDA Service is the internal execution-plane runtime for Chip Orchestra. It keeps the lightweight FastAPI implementation style from the old backend and adapts it into a dedicated, stage-oriented job service with MySQL persistence, Redis queueing, and SSE log streaming.

It is **internal** — the public `orchestrator-service` is the only authenticated gateway and dispatches jobs here through the Go connector.

## Stage-oriented execution

Each job runs a single DAG stage against a standardized per-task workspace and returns a structured report:

| Stage | Runner | Report |
| --- | --- | --- |
| `SIM` | `iverilog -g2012` + `vvp` (RTL + testbench), VCD waveform detection | `SimReport` |
| `LINT` | `iverilog` lint pass over RTL | `LintReport` |
| `SYNTH` / `PNR` / `DRC_LVS` | LibreLane hardening (config synthesis, metrics, GDS/PNG collection, signoff/tapeout readiness) | `SynthReport` / `PnrReport` / `DrcLvsReport` |
| `SIGNOFF` | Structured signoff aggregation | `SignoffReport` |
| _other_ | Mock-compatible fallback | `BaseReport` |

### Workspace layout
```
<WORKSPACE_ROOT>/<task-id>/
  rtl/ tb/ reports/ logs/ waves/ gds/ context/ exports/
```
Structured reports are also persisted to `reports/<stage>_report.json` so the agent-service can collect them as evidence.

### Dependency-injectable runners
Tool invocation goes through a `CommandRunner` protocol (`runner.py`). The default `SubprocessCommandRunner` shells out to the real binaries; **tool binaries do not need to exist for tests** — a missing binary or timeout is returned as a structured failure rather than raising, and tests inject fake runners.

## Endpoints
- `POST /eda/jobs` — accepts `task_id`, `stage`, `spec`, and optional `workspace_root`, `top_module`, `clock_port`, `clock_period`, `stage_options`, `artifacts`
- `GET /eda/jobs/{id}/status`
- `GET /eda/jobs/{id}/report`
- `GET /eda/jobs/{id}/artifacts` — artifact manifest (path, kind, size, mime)
- `GET /eda/jobs/{id}/file?path=...` — safe artifact serving (rejects absolute paths and `..` traversal; serves only under the resolved workspace)
- `GET /eda/jobs/{id}/logs` — SSE
- `DELETE /eda/jobs/{id}`
- `GET /health`

## Environment
| Var | Default | Purpose |
| --- | --- | --- |
| `WORKSPACE_ROOT` | `/tmp/chip-orchestra/workspaces` | Root for per-task workspaces |
| `IVERILOG_PATH` | _(empty)_ | Absolute path override for the Icarus Verilog compiler |
| `IVERILOG_BIN` | `iverilog` | Icarus Verilog compiler binary |
| `VVP_PATH` | _(empty)_ | Absolute path override for the Icarus Verilog runtime |
| `VVP_BIN` | `vvp` | Icarus Verilog runtime binary |
| `LIBRELANE_PATH` | _(empty)_ | Absolute path override for the LibreLane CLI |
| `LIBRELANE_BIN` | `librelane` | LibreLane hardening binary |
| `PDK` | `sky130A` | Target PDK |
| `PDK_ROOT` | `/opt/pdk` | PDK install root |
| `EDA_JOB_TIMEOUT_SIM` | `600` | Simulation timeout (s) |
| `EDA_JOB_TIMEOUT_HARDEN` | `3600` | Hardening timeout (s) |

## Docker image toolchain

The `eda-service` Docker image now mirrors GarudaChip's installation pattern:

- installs **Icarus Verilog** from Debian `apt`
- installs **Nix** in single-user mode inside the image
- installs **LibreLane** from the upstream flake (`github:librelane/librelane`)
- keeps `PDK_ROOT` as a mounted volume so PDK assets can be enabled and reused across container rebuilds

Simulation is ready as soon as the container starts. Hardening is ready once a compatible PDK has been enabled under `PDK_ROOT`.

## Local run
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8002
```

## Tests
```bash
pytest -q
```
