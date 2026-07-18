# EDA Service

The EDA Service is the internal execution-plane runtime for Chip Orchestra. It keeps the lightweight FastAPI implementation style from the old backend and adapts it into a dedicated, stage-oriented job service with MySQL persistence, Redis queueing, and SSE log streaming.

It is **internal** — the public `orchestrator-service` is the only authenticated gateway and dispatches jobs here through the Go connector.

## Stage-oriented execution

Each job runs a single DAG stage against a standardized per-task workspace and returns a structured report:

| Stage | Runner | Report |
| --- | --- | --- |
| `SIM` | `iverilog -g2012` + `vvp` (RTL + testbench), VCD waveform detection | `SimReport` |
| `LINT` | `iverilog` lint pass over RTL | `LintReport` |
| `SYNTH` / `PNR` / `DRC_LVS` | LibreLane hardening (config synthesis, metrics, GDS/PNG collection, signoff/tapeout readiness) with a bounded auto-tuning loop | `SynthReport` / `PnrReport` / `DrcLvsReport` |
| `STA` / `POWER` | OpenSTA (`sta`) static timing / power; falls back to LibreLane metrics if the binary is missing | `StaReport` |
| `GL_SIM` | Gate-level simulation (`iverilog` + post-PNR netlist + PDK cell models) | `GlSimReport` |
| `RENDER` | Best-effort image generation — schematic (yosys/Graphviz), waveform (Matplotlib), GDS layout (gdstk/KLayout), metrics cards | `RenderReport` |
| `SIGNOFF` | Structured signoff aggregation | `SignoffReport` |
| _other_ | Mock-compatible fallback | `BaseReport` |

Stage routing lives in `jobs/manager.py`; report dataclasses in `toolchain/reports.py` all extend `BaseReport`.

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
| `DATABASE_URL` | `mysql+pymysql://chip:chip@mysql:3306/chip_orchestra` | Job persistence (MySQL) |
| `REDIS_URL` | `redis://redis:6379/0` | Job queue and SSE log streaming |
| `PDK` | `gf180mcuD` | Target PDK (GlobalFoundries 180MCU) |
| `PDK_ROOT` | `/opt/pdk` | PDK install root (mounted volume, auto-populated by Volare) |
| `GF180_VOLTAGE` | `3v3` | GF180 corner selection (`3v3` or `5v0`) |
| `EDA_JOB_TIMEOUT_SIM` | `120` | Simulation timeout (s) |
| `EDA_JOB_TIMEOUT_HARDEN` | `3600` | Hardening timeout (s) |
| `IVERILOG_BIN` / `IVERILOG_PATH` | `iverilog` / _(empty)_ | Icarus Verilog compiler binary / absolute-path override |
| `VVP_BIN` / `VVP_PATH` | `vvp` / _(empty)_ | Icarus Verilog runtime binary / absolute-path override |
| `LIBRELANE_BIN` / `LIBRELANE_PATH` | `librelane` / _(empty)_ | LibreLane hardening binary / absolute-path override |
| `STA_BIN` | `sta` | OpenSTA binary |
| `YOSYS_BIN` | `yosys` | Yosys binary (schematic render) |
| `KLAYOUT_BIN` | `klayout` | KLayout binary (GDS render/checks) |
| `_LLN_OVERRIDE_YOSYS` | `/usr/local/bin/yosys-y` | Yosys-with-Python shim used for pyosys/LibreLane steps |

## Docker image toolchain

The `eda-service` Docker image is self-contained — no host EDA tools are needed:

- base image **`python:3.12-slim`**
- **Icarus Verilog, Verilator, yosys, KLayout, Graphviz** installed from Debian `apt`
- **OpenROAD, OpenSTA, Magic, netgen** are copied out of the pinned `hpretl/iic-osic-tools` image (with their Ubuntu shared libraries and a bundled `ld-linux` loader, so they run inside the Debian base regardless of host distro)
- **LibreLane, Volare, gdstk, pyosys, Matplotlib** installed from PyPI (a `yosys -y` shim exposes pyosys)
- the **GF180MCU PDK (`gf180mcuD`)** is installed by **Volare** via `pdk/setup_pdk.sh` into `PDK_ROOT`, which is kept as a mounted volume so PDK assets are reused across container rebuilds

Simulation and lint are ready as soon as the container starts. Hardening (SYNTH/PNR/STA/GL_SIM/RENDER/DRC_LVS) is ready once the PDK has been installed under `PDK_ROOT` on first boot.

## Local run
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8002
```

## Tests
```bash
pytest -q
```
