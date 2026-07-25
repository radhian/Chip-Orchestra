#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Alternative: launch GLM-5.2 with AMD ATOM (AMD's tuned reference server).
# No --trust-remote-code needed (ATOM has built-in GlmMoeDsaForCausalLM).
# Run ON THE GPU NODE.
#
#   HW_PROFILE=mi300x     ./serve_atom.sh   # 8x MI300X FP8  -tp 8
#   HW_PROFILE=mi355x-fp8 ./serve_atom.sh   # 4x MI355X FP8  -tp 4
#   HW_PROFILE=mi355x-fp4 ./serve_atom.sh   # 4x MI355X MXFP4 -tp 4
# ---------------------------------------------------------------------------
set -euo pipefail

HW_PROFILE="${HW_PROFILE:-mi300x}"
LLM_SERVE_PORT="${LLM_SERVE_PORT:-8000}"
HF_TOKEN="${HF_TOKEN:-}"
HF_CACHE_DIR="${HF_CACHE_DIR:-/data/hf-cache}"
IMAGE="${ATOM_IMAGE:-rocm/atom-dev:latest}"

case "$HW_PROFILE" in
  mi300x|mi325x)
    MODEL_ID="${MODEL_ID:-zai-org/GLM-5.2-FP8}"; TP=8
    QUANT='{"global_quant_config":"ptpc_fp8","exclude_layer":["lm_head","model.embed_tokens","*.mlp.gate"]}' ;;
  mi355x-fp8)
    MODEL_ID="${MODEL_ID:-zai-org/GLM-5.2-FP8}"; TP=4
    QUANT='{"global_quant_config":"ptpc_fp8","layer_quant_config":{"model.layers.*.mlp.experts":"per_block_fp8"},"exclude_layer":["lm_head","model.embed_tokens","*.mlp.gate"]}' ;;
  mi355x-fp4)
    MODEL_ID="${MODEL_ID:-amd/GLM-5.2-MXFP4}"; TP=4
    QUANT='{"global_quant_config":"ptpc_fp8","exclude_layer":["lm_head","model.embed_tokens","*.mlp.gate","*expert*"]}' ;;
  *) echo "Unknown HW_PROFILE=$HW_PROFILE" >&2; exit 1 ;;
esac

echo ">> profile=$HW_PROFILE model=$MODEL_ID tp=$TP port=$LLM_SERVE_PORT"
mkdir -p "$HF_CACHE_DIR"

docker run -d --rm \
  --name glm52-atom-rocm \
  --device=/dev/kfd --device=/dev/dri \
  --group-add video --group-add render \
  --ipc=host --shm-size 16g \
  --security-opt seccomp=unconfined --cap-add=SYS_PTRACE \
  -p "${LLM_SERVE_PORT}:8000" \
  -v "${HF_CACHE_DIR}:/root/.cache/huggingface" \
  -e HF_TOKEN="${HF_TOKEN}" -e HUGGING_FACE_HUB_TOKEN="${HF_TOKEN}" \
  -e HF_HOME="/root/.cache/huggingface" \
  -e AITER_QUICK_REDUCE_QUANTIZATION=INT4 \
  -e AITER_USE_FLYDSL_MOE_SORTING=1 \
  "$IMAGE" \
  python -m atom.entrypoints.openai_server \
    --model "$MODEL_ID" \
    --served-model-name GLM-5.2-FP8 \
    --server-port 8000 \
    --kv_cache_dtype fp8 \
    --no-enable_prefix_caching \
    --online_quant_config "$QUANT" \
    --num-speculative-tokens 3 --method mtp \
    -tp "$TP"

echo ">> container started. follow logs:  docker logs -f glm52-atom-rocm"
echo ">> verify:  ./healthcheck.sh"
