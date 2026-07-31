#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Self-host a GLM model on Strix Halo (Ryzen AI Max+ 395, Radeon 8060S iGPU,
# gfx1151, up to 128GB unified memory) via llama.cpp-ROCm, exposing an
# OpenAI-compatible server on :10000 that Chip Orchestra can consume.
#
# gfx1151 is "Preview" in ROCm and requires HSA_OVERRIDE_GFX_VERSION=11.5.1.
# llama.cpp / Ollama are the practical engines here (not the MI300X vLLM path).
#
#   MODEL_REPO=... MODEL_FILE=... bash scripts/serve_strixhalo_glm.sh
#
# The served model id is set with --alias so it appears in /v1/models and
# matches OPENAI_MODEL used by agent-service.
# ---------------------------------------------------------------------------
set -euo pipefail

PORT="${PORT:-10000}"
SERVED_NAME="${SERVED_NAME:-GLM-5.2}"

# Pick a GGUF that FITS in the memory you allocate to the iGPU. Full flagship
# GLM-5.2 (~750B MoE) does NOT fit on a single 128GB node — use a smaller GLM
# variant / heavy quant here, or build a multi-node cluster (see GLM_SELFHOST_AMD.md).
MODEL_REPO="${MODEL_REPO:-unsloth/GLM-4.5-Air-GGUF}"
MODEL_FILE="${MODEL_FILE:-GLM-4.5-Air-Q4_K_M.gguf}"

MODEL_DIR="${MODEL_DIR:-/data/models}"
NGL="${NGL:-999}"                 # offload all layers to the iGPU
CTX="${CTX:-32768}"
# GPU (GTT/unified) memory budget for the iGPU, in MiB. Set in BIOS/kernel too.
GGML_VRAM_MB="${GGML_VRAM_MB:-}"
IMAGE="${LLAMA_IMAGE:-ghcr.io/kyuz0/amd-strix-halo-toolboxes:rocm-7rc-llama}"
HSA_OVERRIDE="${HSA_OVERRIDE_GFX_VERSION:-11.5.1}"

echo ">> Strix Halo GLM server"
echo "   served-name=$SERVED_NAME port=$PORT"
echo "   model=$MODEL_REPO/$MODEL_FILE"
echo "   HSA_OVERRIDE_GFX_VERSION=$HSA_OVERRIDE image=$IMAGE"
mkdir -p "$MODEL_DIR"

docker run -d --rm \
  --name glm-strixhalo \
  --device=/dev/kfd --device=/dev/dri \
  --group-add video --group-add render \
  --ipc=host \
  --security-opt seccomp=unconfined \
  -p "${PORT}:${PORT}" \
  -v "${MODEL_DIR}:/models" \
  -e HSA_OVERRIDE_GFX_VERSION="${HSA_OVERRIDE}" \
  -e HF_HUB_ENABLE_HF_TRANSFER=1 \
  ${GGML_VRAM_MB:+-e GGML_VK_VISIBLE_DEVICES=0} \
  "$IMAGE" \
  llama-server \
    --hf-repo "$MODEL_REPO" \
    --hf-file "$MODEL_FILE" \
    --model "/models/${MODEL_FILE}" \
    --alias "$SERVED_NAME" \
    --host 0.0.0.0 --port "$PORT" \
    --n-gpu-layers "$NGL" \
    --ctx-size "$CTX" \
    --jinja \
    --flash-attn on

echo ">> started. First run downloads the GGUF (can be large)."
echo ">> logs:   docker logs -f glm-strixhalo"
echo ">> verify: BASE=http://localhost:${PORT} OPENAI_MODEL=${SERVED_NAME} ./healthcheck.sh"
