# Self-Hosted GLM-5.2 on AMD ROCm → Chip Orchestra

Fully self-host GLM-5.2 on your AMD/ROCm hardware and point `agent-service` at it,
replacing the Ollama / ZhipuAI-cloud path. **No application code changes** — only
env vars and a serving container.

> Why not Ollama? Ollama (llama.cpp/GGUF) is the wrong engine for a ~750B DSA MoE.
> "Decoupling from Ollama" here means switching `agent-service` from the `ollama`
> provider to the OpenAI-compatible `glm` provider, pointed at your own
> **vLLM-ROCm** / **ATOM** server. `agent-service/llm.py` already speaks that API.

---

## Files

| File | Purpose |
|---|---|
| `.env.selfhosted.example` | Env values to merge into the repo-root `.env`. |
| `docker-compose.vllm-rocm.yml` | vLLM-ROCm GLM-5.2 server (run on the GPU node). |
| `scripts/serve_vllm.sh` | `docker run` launcher, hardware-profile aware. |
| `scripts/serve_atom.sh` | Same, using AMD's ATOM reference server. |
| `scripts/preflight_rocm.sh` | Check ROCm, GPU count, HBM, disk, device access. |
| `scripts/healthcheck.sh` | Verify `/v1/models` + a chat-completion smoke test. |

---

## Hardware profiles

| `HW_PROFILE` | GPUs | Per-GPU HBM | Model | Parallelism | Notes |
|---|---|---|---|---|---|
| `mi300x` | 8× MI300X | 192 GB | `zai-org/GLM-5.2-FP8` | TP8 | Mainstream, validated. Start here. |
| `mi325x` | 8× MI325X | 256 GB | `zai-org/GLM-5.2-FP8` | TP8 | More HBM headroom for KV / concurrency. |
| `mi355x-fp8` | 4× MI355X | 288 GB | `zai-org/GLM-5.2-FP8` | TP4 | CDNA4, 8 TB/s. |
| `mi355x-fp4` | 4× MI355X | 288 GB | `amd/GLM-5.2-MXFP4` | TP4 | Native FP4, **best perf/TCO**. |

FP8 weights ≈ **~750 GB**; MXFP4 ≈ **~375 GB**. Software floor: **ROCm ≥ 6.2** (7.2.x recommended), Ubuntu 22.04, Docker.

---

## Quick start (GPU node)

```bash
cd deploy/selfhosted-llm-rocm
cp .env.selfhosted.example .env         # edit HF_TOKEN, HW_PROFILE, HF_CACHE_DIR
set -a; source .env; set +a

# 1. sanity-check the box
bash scripts/preflight_rocm.sh

# 2a. launch with vLLM (docker run)            -- OR --   2b. docker compose
HW_PROFILE=mi300x bash scripts/serve_vllm.sh
#   docker compose -f docker-compose.vllm-rocm.yml up -d
# (ATOM alternative: HW_PROFILE=mi300x bash scripts/serve_atom.sh)

# 3. first boot downloads ~750GB then loads — watch it
docker logs -f glm52-vllm-rocm

# 4. verify once it's ready
bash scripts/healthcheck.sh
```

---

## Wire it into Chip Orchestra (app stack)

Merge these into the repo-root `.env`, then restart `agent-service`:

```bash
LLM_PROVIDER=glm
OPENAI_BASE_URL=http://host.docker.internal:8000/v1   # or http://<gpu-node-ip>:8000/v1
OPENAI_API_KEY=EMPTY                                  # MUST be non-empty (see gotcha)
OPENAI_MODEL=GLM-5.2-FP8
```

```bash
docker compose up -d agent-service
curl -fsS http://localhost:8001/health
```

The existing `docker-compose.yml` already passes `OPENAI_BASE_URL`, `OPENAI_API_KEY`,
`OPENAI_MODEL` and maps `host.docker.internal` for `agent-service`, so nothing else
needs to change.

---

## Gotchas (read these)

1. **Empty `OPENAI_API_KEY` → silent mock.** `agent-service/llm.py` does
   `if not api_key: return _mock()`. Self-hosted servers don't need a real key,
   but you must set a non-empty placeholder (`EMPTY`), or the agent silently
   returns deterministic mock output that *looks* like a working (but wrong) model.
2. **`--block-size 1` is required** for GLM-5.2's DSA/MLA attention on vLLM-ROCm —
   vLLM errors out otherwise.
3. **`VLLM_ROCM_USE_AITER=1`** (AITER kernels) is what delivers ROCm performance;
   already set in the compose/scripts.
4. **MI355X (gfx950) accuracy caveat (SGLang path):** older ROCm images miscompiled
   a block-FP8 GEMM on CDNA4 and silently corrupted reasoning output. Use a recent
   pinned image and spot-check reasoning quality before trusting it.
5. **Use FP8/MXFP4, never BF16** (~1.5 TB) — doubles memory, halves throughput, no
   quality gain here.

---

## Matching cloud performance — checklist

Output *quality* is identical (same open weights). To match *throughput/latency*:
FP8 (or MXFP4 on MI355X) · **MTP speculative decoding** · **AITER kernels** ·
correct DSA backend (`--block-size 1`) · FP8 KV cache · enough GPUs for your KV
budget (8×MI300X is the floor for TP8).

## Sources
- ATOM GLM-5 recipe: https://github.com/ROCm/ATOM/blob/main/recipes/GLM-5.md
- vLLM GLM-5.2 recipe: https://recipes.vllm.ai/zai-org/GLM-5.2
- vLLM V1 perf optimization (ROCm): https://rocm.docs.amd.com/en/latest/how-to/rocm-for-ai/inference-optimization/vllm-optimization.html
- SGLang GLM-5.2 cookbook: https://docs.sglang.io/cookbook/autoregressive/GLM/GLM-5.2
