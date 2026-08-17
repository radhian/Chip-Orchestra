# Self-Hosted / AMD-Hosted LLM on ROCm → Chip Orchestra

> **Start here for self-hosting GLM on this hardware:** the endpoints are not serving yet, and R9700 (32GB RDNA4) / Strix Halo (128GB APU, gfx1151) are **not** the MI300X datacenter GPUs the `serve_vllm.sh` path assumes. The accurate, runnable plan — including why full flagship GLM-5.2 needs a smaller model or a cluster, the recommended **GLM co-located with agent-service on Strix Halo** topology, and **Podman as the primary tool** — is in `GLM_SELFHOST_AMD.md`. Podman details are in `PODMAN_DEPLOYMENT.md`.

Run Chip Orchestra against OpenAI-compatible LLM endpoints hosted on AMD hardware. The app already supports this path through `LLM_PROVIDER=glm`; no workflow code changes are required.

The current AMD infrastructure is:

| Node | OpenAI-compatible base URL | Recommended role |
|---|---|---|
| R9700 | `http://172.16.1.36:8005/v1` | Primary production endpoint for full Chip Orchestra runs |
| Strix Halo | `http://172.16.1.10:10000/v1` | Secondary endpoint for smoke tests, fallback, smaller/quantized models, or routing experiments |

The served model name must be registered by the model server and visible from `/v1/models`. Chip Orchestra sends `OPENAI_MODEL` as the `model` field in `/v1/chat/completions`, so set it to one of the ids returned by `GET <base>/models` unless your server accepts aliases.

---

## Files

| File | Purpose |
|---|---|
| `AMD_DISTRIBUTED_ARCHITECTURE.md` | Full architecture doc for the Strix Halo agent + R9700 core split |
| `docker-compose.r9700-core.yml` | R9700 stack: MySQL, Redis, orchestrator, EDA, frontend |
| `r9700-core.env.example` | R9700 environment template for the distributed AMD deployment |
| `docker-compose.strix-agent.yml` | Strix Halo stack: remote `agent-service` only |
| `strix-agent.env.example` | Strix Halo environment template for the remote agent stack |
| `amd-infra.env.example` | Single-stack / endpoint-only env profile for the R9700 + Strix Halo LLM endpoints |
| `docker-compose.vllm-rocm.yml` | vLLM-ROCm GLM-5.2 server template for running directly on a GPU node |
| `scripts/check_amd_infra_models.sh` | Checks R9700 and Strix Halo `/v1/models` and runs a chat smoke test |
| `scripts/serve_vllm.sh` | `docker run` launcher, hardware-profile aware |
| `scripts/serve_atom.sh` | Same, using AMD's ATOM reference server |
| `scripts/preflight_rocm.sh` | Check ROCm, GPU count, HBM, disk, device access |
| `scripts/healthcheck.sh` | Verify one OpenAI-compatible endpoint and a chat-completion smoke test |

---

## Recommended deployment plan

The preferred AMD split is now documented in `AMD_DISTRIBUTED_ARCHITECTURE.md`: run `agent-service` on Strix Halo, and run MySQL, Redis, `orchestrator-service`, `eda-service`, and the frontend on R9700. Use the single-stack endpoint profile only when shared storage between the two hosts is not ready yet.

### Phase 0 — endpoint verification

Run this from any host that can reach both AMD nodes:

```bash
cd deploy/selfhosted-llm-rocm
bash scripts/check_amd_infra_models.sh
```

Expected result:

1. `http://172.16.1.36:8005/v1/models` returns at least one model id.
2. `http://172.16.1.10:10000/v1/models` returns at least one model id.
3. A minimal `/v1/chat/completions` request succeeds against each endpoint.

If either `/v1/models` is empty, fix the serving layer first by setting the server's served-model name / model alias. For vLLM this is typically `--served-model-name <MODEL_ID>`; for ATOM it is also `--served-model-name <MODEL_ID>`.

### Phase 1 — distributed AMD deployment: Strix agent + R9700 core

First prepare the shared workspace mount on both hosts at `/srv/chip-orchestra/workspaces`. Then start the R9700 core stack:

```bash
cd deploy/selfhosted-llm-rocm
cp r9700-core.env.example r9700-core.env
# edit secrets and model ids
docker compose --env-file r9700-core.env -f docker-compose.r9700-core.yml up -d --build
```

Start the Strix Halo agent stack:

```bash
cd deploy/selfhosted-llm-rocm
cp strix-agent.env.example strix-agent.env
# edit MYSQL_PASSWORD and OPENAI_MODEL
docker compose --env-file strix-agent.env -f docker-compose.strix-agent.yml up -d --build
```

Verify cross-node health:

```bash
curl -fsS http://172.16.1.36:8080/health
curl -fsS http://172.16.1.36:8002/health
curl -fsS http://172.16.1.10:8001/health
curl -fsS http://172.16.1.10:8001/agent/models
```

### Phase 2 — single-node fallback on R9700

Use R9700 as the first production path because it is the most likely node to have enough dedicated accelerator headroom for long agent turns and EDA repair loops.

```bash
cp deploy/selfhosted-llm-rocm/amd-infra.env.example .env

# IMPORTANT: after checking /v1/models, replace OPENAI_MODEL with the exact id
# returned by http://172.16.1.36:8005/v1/models if it is not literally R9700.
# Example:
# OPENAI_MODEL=GLM-5.2-FP8

docker compose up -d --build
curl -fsS http://localhost:8001/health
curl -fsS http://localhost:8001/agent/models
curl -fsS http://localhost:8080/health
```

The app stack reads:

```bash
LLM_PROVIDER=glm
OPENAI_BASE_URL=http://172.16.1.36:8005/v1
OPENAI_API_KEY=EMPTY
OPENAI_MODEL=<one id from /v1/models>
```

`OPENAI_API_KEY` must be non-empty even for unauthenticated self-hosted servers because the OpenAI-compatible client expects a key.

### Phase 3 — validate an end-to-end chip flow

Run a small design first, not a large SoC. The feasibility gate is not only model reachability; it is whether the endpoint can survive long multi-step orchestration: planning, RTL generation, compile repair, testbench generation, simulation repair, and hardening analysis.

Recommended validation sequence:

```bash
bash tests/smoke_test_nanocgra.sh
```

Then create one UI task for a compact block such as UART FIFO, simple ALU, or NanoCGRA-lite subset. Confirm that the task reaches generated RTL, simulation, and reports without model timeouts.

### Phase 4 — Strix Halo local LLM / routing experiment

After R9700 is stable, test Strix Halo independently:

```bash
BASE=http://172.16.1.10:10000 bash deploy/selfhosted-llm-rocm/scripts/healthcheck.sh
```

If Strix Halo exposes the same production model and passes real task validation, you can switch the app stack by changing:

```bash
OPENAI_BASE_URL=http://172.16.1.10:10000/v1
OPENAI_MODEL=<one id from Strix Halo /v1/models>
```

Best practical use is to keep R9700 as the primary endpoint and use Strix Halo for smaller tasks, demos, smoke tests, or future model-router work. Avoid assuming Strix Halo can run the same huge model or context length unless `/v1/models`, memory, and task-level smoke tests prove it.

---

## Feasibility recommendation

This is feasible if both AMD endpoints are already serving OpenAI-compatible chat completions and `/v1/models` returns the exact model ids. The Chip Orchestra application side only needs env changes and the small `/agent/models` integration now included in this branch.

Best path:

1. Use **R9700 as primary** for full Chip Orchestra runs.
2. Use **Strix Halo as secondary** until it proves it can handle the same context length and latency under real EDA-agent workloads.
3. Register stable served-model names on both nodes, for example `GLM-5.2-FP8`, `Qwen3-Coder`, or another exact production alias, instead of hardware names. Hardware names are useful labels, but model ids should describe the model because they are passed into inference requests.
4. Keep a non-empty `OPENAI_API_KEY=EMPTY` placeholder.
5. Validate with `/v1/models`, one chat completion, `agent-service /agent/models`, then one end-to-end chip task.

A simple two-endpoint failover is not built into the current app runtime; it selects one `OPENAI_BASE_URL` at process start. If automatic fallback is required, add a small OpenAI-compatible router in front of both endpoints or extend `agent-service` with ordered endpoint failover.

---

## Serving your own ROCm node with vLLM / ATOM

Use this section when you need to start the model server on a GPU node instead of consuming the already-running R9700 / Strix Halo endpoints.

### Hardware profiles

| `HW_PROFILE` | GPUs | Per-GPU HBM | Model | Parallelism | Notes |
|---|---|---|---|---|---|
| `mi300x` | 8× MI300X | 192 GB | `zai-org/GLM-5.2-FP8` | TP8 | Mainstream, validated starting point |
| `mi325x` | 8× MI325X | 256 GB | `zai-org/GLM-5.2-FP8` | TP8 | More HBM headroom for KV / concurrency |
| `mi355x-fp8` | 4× MI355X | 288 GB | `zai-org/GLM-5.2-FP8` | TP4 | CDNA4 path |
| `mi355x-fp4` | 4× MI355X | 288 GB | `amd/GLM-5.2-MXFP4` | TP4 | Native FP4, best perf/TCO if supported |

FP8 weights are roughly 750 GB; MXFP4 is roughly 375 GB. Software floor is ROCm 6.2 or newer, with recent ROCm images preferred.

### Quick start on a GPU node

```bash
cd deploy/selfhosted-llm-rocm
set -a; source amd-infra.env.example; set +a

bash scripts/preflight_rocm.sh
HW_PROFILE=mi300x LLM_SERVE_PORT=8005 MODEL_ID=zai-org/GLM-5.2-FP8 bash scripts/serve_vllm.sh

docker logs -f glm52-vllm-rocm
BASE=http://localhost:8005 bash scripts/healthcheck.sh
```

ATOM alternative:

```bash
HW_PROFILE=mi300x LLM_SERVE_PORT=8005 MODEL_ID=zai-org/GLM-5.2-FP8 bash scripts/serve_atom.sh
```

---

## Gotchas

1. **Model id mismatch causes failed requests.** Always copy `OPENAI_MODEL` from `/v1/models`.
2. **`OPENAI_API_KEY` cannot be empty.** Use `EMPTY` for unauthenticated local servers.
3. **Full GLM-5.2 needs large accelerator memory.** Do not assume Strix Halo can host the same full model/context as a multi-GPU ROCm node.
4. **Long context costs real memory.** If tasks time out or OOM, reduce context/model length at the serving layer first.
5. **`--block-size 1` is required** for GLM-5.2 DSA/MLA attention on vLLM-ROCm.
6. **Use FP8/MXFP4 rather than BF16** for this class of model unless you have enough memory headroom and a measured reason.

## Sources

- ATOM GLM-5 recipe: https://github.com/ROCm/ATOM/blob/main/recipes/GLM-5.md
- vLLM GLM-5.2 recipe: https://recipes.vllm.ai/zai-org/GLM-5.2
- vLLM V1 perf optimization on ROCm: https://rocm.docs.amd.com/en/latest/how-to/rocm-for-ai/inference-optimization/vllm-optimization.html
- SGLang GLM-5.2 cookbook: https://docs.sglang.io/cookbook/autoregressive/GLM/GLM-5.2
