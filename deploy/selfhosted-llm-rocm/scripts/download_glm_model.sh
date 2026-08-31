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
# Sharded models:
#   unsloth/GLM-4.5-Air-GGUF stores larger quants (e.g. Q4_K_M ~73GB) as split
#   files, e.g.
#     Q4_K_M/GLM-4.5-Air-Q4_K_M-00001-of-00002.gguf
#     Q4_K_M/GLM-4.5-Air-Q4_K_M-00002-of-00002.gguf
#   Set GLM_MODEL_FILE to the FIRST shard path. llama.cpp auto-loads all
#   consecutive shards when given shard 1 via --model. This script detects the
#   `-00001-of-NNNNN.gguf` pattern and downloads all sibling shards.
#
# Usage:
#   ./scripts/download_glm_model.sh strix-core.rootless.env
#   # or, from any online workstation, then rsync/scp the resulting files to
#   # ${MODEL_DIR} on the Strix Halo host preserving subdir structure.
#
# Env parsing note:
#   podman-compose --env-file uses plain KEY=VALUE parsing (no shell rules),
#   so env files may contain unquoted values with spaces, e.g.
#     DEFAULT_FULL_NAME=Radhian Ferel Armansyah
#   `source`/`.` would try to run `Ferel` as a command, so this script parses
#   only the keys it needs from the file with awk instead of sourcing it.
# ---------------------------------------------------------------------------
set -euo pipefail

ENV_FILE="${1:-}"

_get_env_kv() {
  local env_file="$1" key="$2"
  awk -v k="$key" '
    /^[[:space:]]*#/ {next}
    {
      idx = index($0, "=")
      if (idx == 0) next
      lhs = substr($0, 1, idx - 1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", lhs)
      if (lhs != k) next
      val = substr($0, idx + 1)
      sub(/\r$/, "", val)
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
  _v_model_dir="$(_get_env_kv "${ENV_FILE}" MODEL_DIR || true)"
  _v_repo="$(_get_env_kv "${ENV_FILE}" GLM_MODEL_REPO || true)"
  _v_file="$(_get_env_kv "${ENV_FILE}" GLM_MODEL_FILE || true)"
  [[ -n "${_v_model_dir}" ]] && MODEL_DIR="${_v_model_dir}"
  [[ -n "${_v_repo}"     ]] && GLM_MODEL_REPO="${_v_repo}"
  [[ -n "${_v_file}"     ]] && GLM_MODEL_FILE="${_v_file}"
fi

MODEL_DIR="${MODEL_DIR:-${HOME}/chip-orchestra/models}"
GLM_MODEL_REPO="${GLM_MODEL_REPO:-unsloth/GLM-4.5-Air-GGUF}"
# NOTE: this file lives in a subdir on HF and is split into 2 shards. Setting
# it to shard 1 makes llama.cpp auto-load shard 2 at runtime.
GLM_MODEL_FILE="${GLM_MODEL_FILE:-Q4_K_M/GLM-4.5-Air-Q4_K_M-00001-of-00002.gguf}"
HF_ENDPOINT="${HF_ENDPOINT:-https://huggingface.co}"

echo "==> Repo:    ${GLM_MODEL_REPO}"
echo "==> File:    ${GLM_MODEL_FILE}"
echo "==> Target:  ${MODEL_DIR}/${GLM_MODEL_FILE}"
mkdir -p "${MODEL_DIR}"
chmod 0777 "${MODEL_DIR}" 2>/dev/null || true

# Detect shard pattern -00001-of-NNNNN.gguf → expand to full shard list.
FILES=("${GLM_MODEL_FILE}")
shard_re='(.*)-([0-9]{5})-of-([0-9]{5})\.gguf$'
if [[ "${GLM_MODEL_FILE}" =~ ${shard_re} ]]; then
  base="${BASH_REMATCH[1]}"
  idx=$((10#${BASH_REMATCH[2]}))
  total=$((10#${BASH_REMATCH[3]}))
  if (( idx == 1 && total > 1 )); then
    FILES=()
    for ((i=1; i<=total; i++)); do
      printf -v part '%05d' "$i"
      printf -v tot  '%05d' "$total"
      FILES+=("${base}-${part}-of-${tot}.gguf")
    done
    echo "==> Detected sharded GGUF: will download ${total} shards:"
    for f in "${FILES[@]}"; do echo "     - ${f}"; done
  fi
fi

_download_one() {
  local relpath="$1"
  local dest="${MODEL_DIR}/${relpath}"
  local url="${HF_ENDPOINT}/${GLM_MODEL_REPO}/resolve/main/${relpath}"
  mkdir -p "$(dirname "${dest}")"

  if [[ -s "${dest}" ]]; then
    echo "==> Already present: $(du -h "${dest}" | cut -f1) ${dest}"
    return 0
  fi

  if command -v huggingface-cli >/dev/null 2>&1; then
    echo "==> huggingface-cli: ${relpath}"
    huggingface-cli download "${GLM_MODEL_REPO}" "${relpath}" \
      --local-dir "${MODEL_DIR}" --local-dir-use-symlinks False
  else
    echo "==> curl: ${url}"
    if ! curl -fL --retry 5 --retry-delay 5 -C - -o "${dest}" "${url}"; then
      echo "" >&2
      echo "ERROR: failed to download '${relpath}' from ${GLM_MODEL_REPO}." >&2
      echo "       Listing repo root to help pick a valid path:" >&2
      curl -sSf "${HF_ENDPOINT}/api/models/${GLM_MODEL_REPO}/tree/main" \
        | tr ',' '\n' | grep -oE '"path":"[^"]+"' | sed 's/"path":"/  /; s/"$//' >&2 || true
      echo "" >&2
      echo "Tip: set GLM_MODEL_FILE to a path from the listing above (use the" >&2
      echo "     first shard for split files, e.g. Q4_K_M/GLM-4.5-Air-Q4_K_M-00001-of-00002.gguf)." >&2
      return 1
    fi
  fi

  if [[ ! -s "${dest}" ]]; then
    echo "ERROR: download produced empty file at ${dest}" >&2
    return 1
  fi
  echo "    -> $(du -h "${dest}" | cut -f1) ${dest}"
}

for f in "${FILES[@]}"; do
  _download_one "${f}"
done

echo ""
echo "==> Done. Files under ${MODEL_DIR}:"
for f in "${FILES[@]}"; do
  ls -lh "${MODEL_DIR}/${f}" 2>/dev/null || true
done
echo ""
echo "Next: start the stack with the same env file. glm-server mounts"
echo "\${MODEL_DIR} → /models, and llama.cpp reads --model /models/\${GLM_MODEL_FILE}."
echo "For split GGUFs, pointing at shard 1 is sufficient — llama.cpp auto-loads"
echo "sibling shards from the same directory."
