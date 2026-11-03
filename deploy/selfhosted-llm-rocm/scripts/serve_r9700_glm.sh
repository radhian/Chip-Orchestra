#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Self-host a GLM model on the R9700 (Radeon AI PRO R9700, Navi 48 / RDNA4,
# gfx120x, 32GB GDDR6) via llama.cpp-ROCm, exposing an OpenAI-compatible
# server on :8005 that Chip Orchestra can consume.
#
# 32GB VRAM is the hard limit: pick a GGUF whose weights + KV cache fit under
# ~30GB. Full GLM-5.2 flagship does NOT fit here (see GLM_SELFHOST_AMD.md).
# Good fits: ~30B-class at Q4, or a smaller GLM variant.
#
#   MODEL_REPO=... MODEL_FILE=... bash scripts/serve_r9700_glm.sh
# ---------------------------------------------------------------------------
set -euo pipefail

PORT="${PORT:-8005}"
SERVED_NAME="${SERVED_NAME:-GLM-5.2}"

MODEL_REPO="${MODEL_REPO:-unsloth/GLM-4-32B-0414-GGUF}"
MODEL_FILE="${MODEL_FILE:-GLM-4-32B-0414-Q4_K_M.gguf}"

MODEL_DIR="${MODEL_DIR:-/data/models}"
NGL="${NGL:-999}"
CTX="${CTX:-32768}"
IMAGE="${LLAMA_IMAGE:-ghcr.io/ggml-org/llama.cpp:server-rocm}"
# RDNA4 (gfx1201) is native in ROCm 7; override only if your build needs it.
HSA_OVERRIDE="${HSA_OVERRIDE_GFX_VERSION:-}"

echo ">> R9700 GLM server"
echo "   served-name=$SERVED_NAME port=$PORT"
echo "   model=$MODEL_REPO/$MODEL_FILE image=$IMAGE"
mkdir -p "$MODEL_DIR"

docker run -d --rm \
  --name glm-r9700 \
  --device=/dev/kfd --device=/dev/dri \
  --group-add video --group-add render \
  --ipc=host \
  --security-opt seccomp=unconfined \
  -p "${PORT}:${PORT}" \
  -v "${MODEL_DIR}:/models" \
  ${HSA_OVERRIDE:+-e HSA_OVERRIDE_GFX_VERSION="${HSA_OVERRIDE}"} \
  -e HF_HUB_ENABLE_HF_TRANSFER=1 \
  "$IMAGE" \
  -hf "${MODEL_REPO}:${MODEL_FILE}" \
  --model "/models/${MODEL_FILE}" \
  --alias "$SERVED_NAME" \
  --host 0.0.0.0 --port "$PORT" \
  --n-gpu-layers "$NGL" \
  --ctx-size "$CTX" \
  --jinja \
  --flash-attn on

echo ">> started. First run downloads the GGUF."
echo ">> logs:   docker logs -f glm-r9700"
echo ">> verify: BASE=http://localhost:${PORT} OPENAI_MODEL=${SERVED_NAME} ./healthcheck.sh"
