#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Check AMD-hosted OpenAI-compatible endpoints and their /v1/models registry.
# Defaults match the current R9700 + Strix Halo infrastructure.
#
#   bash scripts/check_amd_infra_models.sh
#   AMD_LLM_ENDPOINTS="R9700=http://host:8000/v1" bash scripts/check_amd_infra_models.sh
# ---------------------------------------------------------------------------
set -euo pipefail

AMD_LLM_ENDPOINTS="${AMD_LLM_ENDPOINTS:-R9700=http://172.16.1.36:8005/v1 Strix-Halo=http://172.16.1.10:10000/v1}"
OPENAI_API_KEY="${OPENAI_API_KEY:-EMPTY}"

fail=0
for entry in $AMD_LLM_ENDPOINTS; do
  name="${entry%%=*}"
  base="${entry#*=}"
  base="${base%/}"
  echo "== $name @ $base =="

  if ! models_json=$(curl -fsS -H "Authorization: Bearer ${OPENAI_API_KEY}" "${base}/models"); then
    echo "FAIL: cannot reach ${base}/models"
    fail=1
    echo
    continue
  fi

  printf '%s\n' "$models_json" | python3 -c 'import json,sys; data=json.load(sys.stdin); ids=[m.get("id", "") for m in data.get("data", []) if m.get("id")]; print("registered models:"); [print("  - " + model_id) for model_id in ids] or print("  (none)")'

  first_model=$(printf '%s\n' "$models_json" | python3 -c 'import json,sys; data=json.load(sys.stdin); ids=[m.get("id", "") for m in data.get("data", []) if m.get("id")]; print(ids[0] if ids else "")')
  if [ -z "$first_model" ]; then
    echo "FAIL: /v1/models returned no model ids; register or expose at least one model before using this endpoint."
    fail=1
    echo
    continue
  fi

  echo "smoke model: $first_model"
  if ! curl -fsS "${base}/chat/completions" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${OPENAI_API_KEY}" \
    -d "{\"model\":\"${first_model}\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the single word: OK\"}],\"max_tokens\":16,\"temperature\":0}" \
    | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("choices", [{}])[0].get("message", {}).get("content", data))'; then
    echo "FAIL: chat completion failed for $first_model"
    fail=1
  fi
  echo
done

if [ "$fail" -eq 0 ]; then
  echo "AMD endpoint check: PASS"
else
  echo "AMD endpoint check: FAIL"
fi
exit "$fail"
