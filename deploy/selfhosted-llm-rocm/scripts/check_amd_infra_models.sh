#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Check AMD-hosted OpenAI-compatible endpoints and their /v1/models registry.
# Defaults match the current R9700 + Strix Halo infrastructure.
#
#   bash scripts/check_amd_infra_models.sh
#   AMD_LLM_ENDPOINTS="R9700=http://host:8000/v1" bash scripts/check_amd_infra_models.sh
# ---------------------------------------------------------------------------
set -euo pipefail

AMD_LLM_ENDPOINTS="${AMD_LLM_ENDPOINTS:-RX7900XT=http://172.16.100.2:10000/v1}"
OPENAI_API_KEY="${OPENAI_API_KEY:-EMPTY}"
PREFERRED_SMOKE_MODEL="${PREFERRED_SMOKE_MODEL:-${OPENAI_MODEL:-Qwen3.8-27B-multimodal}}"

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

  registered_models=$(printf '%s\n' "$models_json" | python3 -c 'import json,sys; data=json.load(sys.stdin); ids=[m.get("id", "") for m in data.get("data", []) if m.get("id")]; print("\n".join(ids))')
  printf '%s\n' "$registered_models" | python3 -c 'import sys; ids=[line.strip() for line in sys.stdin if line.strip()]; print("registered models:"); [print("  - " + model_id) for model_id in ids] or print("  (none)")'

  first_model=$(printf '%s\n' "$registered_models" | head -n 1)
  if [ -z "$first_model" ]; then
    echo "FAIL: /v1/models returned no model ids; register or expose at least one model before using this endpoint."
    fail=1
    echo
    continue
  fi

  smoke_model="$first_model"
  if printf '%s\n' "$registered_models" | grep -Fxq "$PREFERRED_SMOKE_MODEL"; then
    smoke_model="$PREFERRED_SMOKE_MODEL"
  fi

  echo "smoke model: $smoke_model"
  if ! completion_json=$(curl -fsS "${base}/chat/completions" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${OPENAI_API_KEY}" \
    -d "{\"model\":\"${smoke_model}\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the single word: OK\"}],\"max_tokens\":16,\"temperature\":0}"); then
    echo "FAIL: chat completion request failed for $smoke_model"
    fail=1
    echo
    continue
  fi

  if ! printf '%s\n' "$completion_json" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("choices", [{}])[0].get("message", {}).get("content", data))'; then
    echo "FAIL: chat completion returned invalid JSON for $smoke_model"
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
