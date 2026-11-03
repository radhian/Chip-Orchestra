#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Launch GLM-5.2 on AMD ROCm with vLLM via `docker run` (no compose needed).
# Hardware-profile aware. Run ON THE GPU NODE.
#
#   HW_PROFILE=mi300x     ./serve_vllm.sh   # 8x MI300X (192GB) FP8 TP8
#   HW_PROFILE=mi325x     ./serve_vllm.sh   # 8x MI325X (256GB) FP8 TP8
#   HW_PROFILE=mi355x-fp8 ./serve_vllm.sh   # 4x MI355X (288GB) FP8 TP4
#   HW_PROFILE=mi355x-fp4 ./serve_vllm.sh   # 4x MI355X (288GB) MXFP4 TP4  (best TCO)
# ---------------------------------------------------------------------------
set -euo pipefail

HW_PROFILE="${HW_PROFILE:-mi300x}"
LLM_SERVE_PORT="${LLM_SERVE_PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-524288}"
HF_TOKEN="${HF_TOKEN:-}"
HF_CACHE_DIR="${HF_CACHE_DIR:-/data/hf-cache}"
IMAGE="${VLLM_IMAGE:-docker.io/rocm/vllm:latest}"

case "$HW_PROFILE" in
  mi300x|mi325x)
    MODEL_ID="${MODEL_ID:-zai-org/GLM-5.2-FP8}"; TP=8; KV="fp8_e4m3" ;;
  mi355x-fp8)
    MODEL_ID="${MODEL_ID:-zai-org/GLM-5.2-FP8}"; TP=4; KV="fp8_e4m3" ;;
  mi355x-fp4)
    MODEL_ID="${MODEL_ID:-amd/GLM-5.2-MXFP4}";  TP=4; KV="fp8_e4m3" ;;
  *) echo "Unknown HW_PROFILE=$HW_PROFILE" >&2; exit 1 ;;
esac

echo ">> profile=$HW_PROFILE model=$MODEL_ID tp=$TP port=$LLM_SERVE_PORT"
mkdir -p "$HF_CACHE_DIR"

docker run -d --rm \
  --name glm52-vllm-rocm \
  --device=/dev/kfd --device=/dev/dri \
  --group-add video --group-add render \
  --ipc=host --shm-size 16g \
  --security-opt seccomp=unconfined --cap-add=SYS_PTRACE \
  -p "${LLM_SERVE_PORT}:8000" \
  -v "${HF_CACHE_DIR}:/root/.cache/huggingface" \
  -e HF_TOKEN="${HF_TOKEN}" -e HUGGING_FACE_HUB_TOKEN="${HF_TOKEN}" \
  -e HF_HOME="/root/.cache/huggingface" \
  -e VLLM_ROCM_USE_AITER=1 \
  -e VLLM_ROCM_USE_AITER_FUSION_SHARED_EXPERTS=1 \
  "$IMAGE" \
  vllm serve "$MODEL_ID" \
    --served-model-name GLM-5.2-FP8 \
    --tensor-parallel-size "$TP" \
    --kv-cache-dtype "$KV" \
    --block-size 1 \
    --speculative-config.method mtp \
    --speculative-config.num_speculative_tokens 5 \
    --reasoning-parser glm45 \
    --tool-call-parser glm47 --enable-auto-tool-choice \
    --gpu-memory-utilization 0.80 \
    --max-model-len "$MAX_MODEL_LEN" \
    --linear-backend aiter --moe-backend aiter \
    --host 0.0.0.0 --port 8000

echo ">> container started. First boot downloads ~750GB (FP8) and can take 20-40 min."
echo ">> follow logs:  docker logs -f glm52-vllm-rocm"
echo ">> verify:       ./healthcheck.sh"
