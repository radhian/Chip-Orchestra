# Self-Hosted / AMD-Hosted LLM on ROCm → Chip Orchestra

> **Primary architecture today:** run the full Chip Orchestra stack on the RX 7900 XT VM and point `agent-service` at the already-running local OpenAI-compatible endpoint. The default single-node profile is `LLM_PROVIDER=openai-compatible`, `OPENAI_BASE_URL=http://172.16.100.2:10000/v1`, and `OPENAI_MODEL=Qwen3.8-27B-multimodal`.
>
> **Legacy / reference architecture:** the older R9700 + Strix Halo split remains useful as background material for future multi-node deployments, but it is no longer the default path for this branch. The large-model self-hosting notes for MI300-class hardware are still documented in `GLM_SELFHOST_AMD.md`, and Podman runtime notes remain in `PODMAN_DEPLOYMENT.md`.

Run Chip Orchestra against OpenAI-compatible LLM endpoints hosted on AMD hardware. For the current branch, the intended production profile is a **single-node RX 7900 XT VM** where the model endpoint, `agent-service`, and the rest of the application stack all live on the same host.

The current target infrastructure is:

| Host | OpenAI-compatible base URL | Recommended role |
|---|---|---|
| RX 7900 XT VM | `http://172.16.100.2:10000/v1` | Primary and recommended endpoint for the full Chip Orchestra stack |
| Distributed AMD split (optional) | Varies by deployment | Secondary / future topology for experiments or larger multi-node layouts |

The served model name must be registered by the model server and visible from `/v1/models`. Chip Orchestra sends `OPENAI_MODEL` as the `model` field in `/v1/chat/completions`, so set it to one of the ids returned by `GET <base>/models` unless your server accepts aliases.

---

## Files

| File | Purpose |
|---|---|
| `AMD_DISTRIBUTED_ARCHITECTURE.md` | Reference architecture doc for the older Strix Halo agent + R9700 core split |
| `docker-compose.r9700-core.yml` | Core stack compose used by both the distributed deployment and the RX 7900 XT single-node overlay |
| `r9700-core.env.example` | Distributed deployment environment template for the core stack |
| `docker-compose.strix-agent.yml` | `agent-service` compose used for remote-agent mode and for the RX 7900 XT single-node overlay |
| `strix-agent.env.example` | Remote-agent environment template |
| `docker-compose.strix-single-node.rootless.yml` | Rootless single-node override for the RX 7900 XT VM |
| `strix-core.rootless.env` | Current single-node RX 7900 XT environment file |
| `docker-compose.vllm-rocm.yml` | Legacy MI300-class vLLM-ROCm GLM-5.2 server template |
| `scripts/check_amd_infra_models.sh` | Checks the current OpenAI-compatible endpoint(s) and runs a chat smoke test |
| `scripts/serve_vllm.sh` | Legacy `docker run` launcher for MI300-class vLLM deployments |
| `scripts/serve_atom.sh` | Legacy `docker run` launcher using AMD's ATOM reference server |
| `scripts/preflight_rocm.sh` | Check ROCm, GPU count, disk, and device access before self-hosting on supported ROCm hardware |
| `scripts/healthcheck.sh` | Verify one OpenAI-compatible endpoint and a chat-completion smoke test |

---

## Recommended deployment plan

The current recommended architecture is the **single-node RX 7900 XT VM**. Run the OpenAI-compatible model endpoint, `agent-service`, MySQL, Redis, `orchestrator-service`, `eda-service`, and the frontend on the same host. Keep the older distributed Strix Halo + R9700 split as an optional secondary topology for future experiments or larger multi-node work.

### Phase 0 — verify the current single-node endpoint

Run this from the RX 7900 XT VM, or from any machine that can reach the VM on `172.16.100.2`:

```bash
cd deploy/selfhosted-llm-rocm
bash scripts/check_amd_infra_models.sh
```

Expected result:

1. `http://172.16.100.2:10000/v1/models` returns at least one model id.
2. A minimal `/v1/chat/completions` request succeeds.
3. The served model list includes the id you plan to use from Chip Orchestra, ideally `Qwen3.8-27B-multimodal`.

If `/v1/models` is empty, fix the serving layer first by setting the server's served-model name / model alias. For vLLM this is typically `--served-model-name <MODEL_ID>`; for ATOM it is also `--served-model-name <MODEL_ID>`.

### Phase 1 — recommended single-node RX 7900 XT deployment

Use the single-node rootless profile on the RX 7900 XT VM when the OpenAI-compatible endpoint is already available locally:

```bash
cd deploy/selfhosted-llm-rocm
podman-compose --env-file strix-core.rootless.env \
  -f docker-compose.r9700-core.yml \
  -f docker-compose.strix-agent.yml \
  -f docker-compose.strix-single-node.rootless.yml \
  up -d --build
```

This profile assumes:

```bash
LLM_PROVIDER=openai-compatible
OPENAI_BASE_URL=http://172.16.100.2:10000/v1
OPENAI_MODEL=Qwen3.8-27B-multimodal
OPENAI_API_KEY=EMPTY
```

Validate health:

```bash
curl -fsS http://172.16.100.2:8080/health
curl -fsS http://172.16.100.2:8001/health
curl -fsS http://172.16.100.2:8001/agent/models
curl -fsS http://172.16.100.2:10000/v1/models
```

### Phase 2 — optional distributed AMD deployment: Strix agent + R9700 core

Use this only when you explicitly want a multi-node topology. First prepare the shared workspace mount on both hosts at `/srv/chip-orchestra/workspaces`. Then start the R9700 core stack:

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

### Phase 3 — validate an end-to-end chip flow

Run a small design first, not a large SoC. The feasibility gate is not only model reachability; it is whether the endpoint can survive long multi-step orchestration: planning, RTL generation, compile repair, testbench generation, simulation repair, and hardening analysis.

Recommended validation sequence:

```bash
bash tests/smoke_test_nanocgra.sh
```

Then create one UI task for a compact block such as UART FIFO, simple ALU, or NanoCGRA-lite subset. Confirm that the task reaches generated RTL, simulation, and reports without model timeouts.

### Phase 4 — optional alternate-endpoint experiment

Only after the RX 7900 XT single-node path is stable should you test a second endpoint or router configuration.

For a second endpoint, verify it independently first:

```bash
BASE=http://<alternate-host>:10000 bash deploy/selfhosted-llm-rocm/scripts/healthcheck.sh
```

If that alternate endpoint passes real task validation, you can switch Chip Orchestra by changing:

```bash
OPENAI_BASE_URL=http://<alternate-host>:10000/v1
OPENAI_MODEL=<one id from /v1/models on the alternate endpoint>
```

The current runtime still selects one `OPENAI_BASE_URL` at process start. If you need automatic failover or model routing, place a small OpenAI-compatible router in front of multiple backends or extend `agent-service` with ordered endpoint failover.

---

## Feasibility recommendation

This is feasible today for the **single-node RX 7900 XT architecture** as long as the local endpoint on `172.16.100.2:10000` is already serving OpenAI-compatible chat completions and `/v1/models` returns the exact model id Chip Orchestra will send, ideally `Qwen3.8-27B-multimodal`.

Best path:

1. Use the **RX 7900 XT VM as the primary and recommended deployment**.
2. Keep the endpoint configuration explicit: `LLM_PROVIDER=openai-compatible`, `OPENAI_BASE_URL=http://172.16.100.2:10000/v1`, `OPENAI_MODEL=Qwen3.8-27B-multimodal`, and `OPENAI_API_KEY=EMPTY`.
3. Validate in order with `/v1/models`, one chat completion, `agent-service /agent/models`, then one end-to-end chip task.
4. Treat the Strix Halo + R9700 split as optional follow-on work, not as the baseline architecture for this branch.
5. If you later need multi-endpoint routing or failover, add a router layer or extend `agent-service`; do not describe it as built into the current runtime.

---

## Serving your own ROCm node with vLLM / ATOM

Use this section only when you need to stand up a **new** ROCm model server yourself instead of consuming the already-running OpenAI-compatible endpoint on the RX 7900 XT VM. The scripts below are still useful as reference material for MI300-class hardware or future larger deployments, but they are not the primary day-one path for the current single-node architecture.

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


---

## Updating and redeploying

Use this workflow after copying the fix into your checkout. It preserves the persistent database, Redis data, model files, and design workspaces; only application images are rebuilt.

```bash
cd Chip-Orchestra
cp deploy/selfhosted-llm-rocm/strix-core.rootless.env \
   deploy/selfhosted-llm-rocm/strix-core.rootless.env.local
```

Edit `strix-core.rootless.env.local` for the target host. At minimum, verify:

```bash
OPENAI_BASE_URL=http://172.16.100.2:10000/v1
OPENAI_MODEL=Qwen3.8-27B-multimodal
OPENAI_API_KEY=EMPTY
OPENAI_TIMEOUT=600
OPENAI_MAX_TOKENS=8192
WORKSPACE_HOST_PATH=/home/efison-radhi/chip-orchestra/workspaces
MODEL_DIR=/home/efison-radhi/chip-orchestra/models
```

Verify the existing llama-swap endpoint before rebuilding Chip Orchestra:

```bash
cd deploy/selfhosted-llm-rocm
BASE=http://172.16.100.2:10000 \
OPENAI_MODEL=Qwen3.8-27B-multimodal \
bash scripts/healthcheck.sh
```

Update the checkout and redeploy the application containers:

```bash
cd /path/to/Chip-Orchestra
git pull --ff-only
cd deploy/selfhosted-llm-rocm
podman-compose --env-file strix-core.rootless.env.local \
  -f docker-compose.r9700-core.yml \
  -f docker-compose.strix-agent.yml \
  -f docker-compose.strix-single-node.rootless.yml \
  build agent-service orchestrator-service frontend
podman-compose --env-file strix-core.rootless.env.local \
  -f docker-compose.r9700-core.yml \
  -f docker-compose.strix-agent.yml \
  -f docker-compose.strix-single-node.rootless.yml \
  up -d
```

Docker users can replace `podman-compose` with `docker compose`. Do not add the `strix-glm` compose files when llama-swap is already running on port `10000`; those files launch another model server and can conflict with it.

Post-deployment verification:

```bash
curl -fsS http://172.16.100.2:8001/health
curl -fsS http://172.16.100.2:8001/agent/models
curl -fsS http://172.16.100.2:8001/agent/llm/status
```

The last response reports llama-swap health and currently loaded models. To release GPU memory through llama-swap:

```bash
# Unload one model
curl -fsS -X POST http://172.16.100.2:8001/agent/llm/unload \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen3.8-27B-multimodal"}'

# Unload all models
curl -fsS -X POST http://172.16.100.2:8001/agent/llm/unload \
  -H 'Content-Type: application/json' \
  -d '{}'
```

For rollback, check out the previous revision and rerun the same `build` and `up -d` commands. Persistent volumes and workspace files are not deleted by this procedure.


### Login request shows a red network failure

A red `login` request with no HTTP status means the browser did not receive an HTTP response; it is not an incorrect-password response. Check the API container and firewall before resetting credentials:

```bash
cd deploy/selfhosted-llm-rocm
podman-compose --env-file strix-core.rootless.env.local \
  -f docker-compose.r9700-core.yml \
  -f docker-compose.strix-agent.yml \
  -f docker-compose.strix-single-node.rootless.yml \
  ps
podman-compose --env-file strix-core.rootless.env.local \
  -f docker-compose.r9700-core.yml \
  -f docker-compose.strix-agent.yml \
  -f docker-compose.strix-single-node.rootless.yml \
  logs --tail 200 orchestrator-service
curl -v http://127.0.0.1:8080/health
curl -v http://172.16.100.2:8080/health
```

If loopback works but the LAN URL fails, apply the repository firewall rules from the repository root:

```bash
sudo LAN_CIDR=172.16.100.0/24 \
  PODMAN_CIDR=10.90.0.0/24 \
  bash scripts/ufw-core.sh
```

Then rebuild the frontend so its compile-time API URL matches the browser-visible host:

```bash
VITE_API_BASE_URL=http://172.16.100.2:8080 \
podman-compose --env-file strix-core.rootless.env.local \
  -f docker-compose.r9700-core.yml \
  -f docker-compose.strix-agent.yml \
  -f docker-compose.strix-single-node.rootless.yml \
  build --no-cache frontend
podman-compose --env-file strix-core.rootless.env.local \
  -f docker-compose.r9700-core.yml \
  -f docker-compose.strix-agent.yml \
  -f docker-compose.strix-single-node.rootless.yml \
  up -d frontend
```

Do not run `scripts/rebuild_frontend_localhost.sh` for LAN access. That helper deliberately bakes `http://localhost:8080` into the frontend and is only for SSH local-port-forward mode.
