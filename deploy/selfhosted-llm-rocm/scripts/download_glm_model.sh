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
#
# Env parsing note:
#   podman-compose --env-file uses simple KEY=VALUE parsing (no shell rules),
#   so env files can contain unquoted values with spaces, e.g.
#     DEFAULT_FULL_NAME=Radhian Ferel Armansyah
#   That is invalid for `source`/`.`, which would try to run `Ferel` as a
#   command. So this script parses only the exact keys it needs from the file
#   using awk, rather than sourcing it.
# ---------------------------------------------------------------------------
set -euo pipefail

ENV_FILE="${1:-}"

_get_env_kv() {
  # Print the raw value of KEY from an env file, respecting the last occurrence,
  # stripping surrounding single/double quotes, and ignoring commented lines.
  local env_file="$1" key="$2"
  awk -v k="$key" '
    /^[[:space:]]*#/ {next}
    {
      # match "KEY=" at start (allow leading spaces)
      idx = index($0, "=")
      if (idx == 0) next
      lhs = substr($0, 1, idx - 1)
      # strip whitespace from lhs
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", lhs)
      if (lhs != k) next
      val = substr($0, idx + 1)
      # strip a trailing CR (Windows line endings)
      sub(/\r$/, "", val)
      # unquote if fully wrapped in single or double quotes
      n = length(val)
      if (n >= 2) {
        first = substr(val, 1, 1)
        last  = substr(val, n, 1)
        if ((first == "\"" && last == "\"") || (first == "'"'"'" && last == "'"'"'")) {
          val = substr(val, 2, n - 2)
        }
      }
      last_val = val
      found = 1
    }
    END { if (found) print last_val }
  ' "$env_file"
}

if [[ -n "${ENV_FILE}" ]]; then
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: env file '${ENV_FILE}' not found." >&2
    exit 1
  fi
  # Pull only the keys we care about — do NOT source the file (values may
  # contain spaces, which is legal for podman-compose --env-file but not for
  # POSIX shell).
  _v_model_dir="$(_get_env_kv "${ENV_FILE}" MODEL_DIR || true)"
  _v_repo="$(_get_env_kv "${ENV_FILE}" GLM_MODEL_REPO || true)"
  _v_file="$(_get_env_kv "${ENV_FILE}" GLM_MODEL_FILE || true)"
  [[ -n "${_v_model_dir}" ]] && MODEL_DIR="${_v_model_dir}"
  [[ -n "${_v_repo}"     ]] && GLM_MODEL_REPO="${_v_repo}"
  [[ -n "${_v_file}"     ]] && GLM_MODEL_FILE="${_v_file}"
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
