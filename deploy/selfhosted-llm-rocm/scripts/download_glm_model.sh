#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Pre-download the GLM GGUF model to the host MODEL_DIR before starting the
# rootless single-node stack.
#
# Why this exists:
#   glm-server (llama.cpp-ROCm) auto-downloads from Hugging Face via `-hf`, but
#   on hosts with restricted egress the download fails with:
#     E get_repo_commit: HTTPLIB failed: Could not establish connection
#     E gguf_init_from_file: failed to open GGUF file '/models/...' (No such file or directory)
#   Pre-downloading once puts the file at exactly the path the container reads
#   via `--model /models/${GLM_MODEL_FILE}`, so the network fetch is skipped.
#
# Usage:
#   ./scripts/download_glm_model.sh strix-core.rootless.env
#   # or, from any online workstation, then rsync/scp the resulting file to
#   # ${MODEL_DIR} on the Strix Halo host.
#
# The script prefers huggingface-cli (fastest, resumable). If that is not
# available it falls back to curl against the HF resolve URL.
# ---------------------------------------------------------------------------
set -euo pipefail

ENV_FILE="${1:-}"
if [[ -n "${ENV_FILE}" ]]; then
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: env file '${ENV_FILE}' not found." >&2
    exit 1
  fi
  # shellcheck disable=SC2046
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

MODEL_DIR="${MODEL_DIR:-${HOME}/chip-orchestra/models}"
GLM_MODEL_REPO="${GLM_MODEL_REPO:-unsloth/GLM-4.5-Air-GGUF}"
GLM_MODEL_FILE="${GLM_MODEL_FILE:-GLM-4.5-Air-Q4_K_M.gguf}"

echo "==> Target: ${MODEL_DIR}/${GLM_MODEL_FILE}"
echo "==> Source: hf://${GLM_MODEL_REPO}/${GLM_MODEL_FILE}"

mkdir -p "${MODEL_DIR}"
chmod 0777 "${MODEL_DIR}" 2>/dev/null || true

TARGET="${MODEL_DIR}/${GLM_MODEL_FILE}"
if [[ -s "${TARGET}" ]]; then
  echo "==> Already present: $(du -h "${TARGET}" | cut -f1) ${TARGET}"
  echo "    Skipping download. Delete the file first to re-fetch."
  exit 0
fi

if command -v huggingface-cli >/dev/null 2>&1; then
  echo "==> Using huggingface-cli"
  huggingface-cli download "${GLM_MODEL_REPO}" "${GLM_MODEL_FILE}" \
    --local-dir "${MODEL_DIR}" --local-dir-use-symlinks False
else
  echo "==> huggingface-cli not found — falling back to curl"
  URL="https://huggingface.co/${GLM_MODEL_REPO}/resolve/main/${GLM_MODEL_FILE}"
  curl -fL --retry 5 --retry-delay 5 -C - -o "${TARGET}" "${URL}"
fi

if [[ ! -s "${TARGET}" ]]; then
  echo "ERROR: download did not produce a non-empty file at ${TARGET}" >&2
  exit 1
fi

echo "==> Done. $(du -h "${TARGET}" | cut -f1) at ${TARGET}"
echo "    Next: start the stack with the same env file — llama.cpp will now"
echo "    skip the HF fetch and use the local file via --model /models/${GLM_MODEL_FILE}."
