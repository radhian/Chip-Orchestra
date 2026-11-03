#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://172.16.100.2:10000}"
BASE="${BASE%/}"
BASE="${BASE%/v1}"
API_KEY="${OPENAI_API_KEY:-EMPTY}"
MODEL="${OPENAI_MODEL:-Qwen3.8-27B-multimodal}"
AUTH=(-H "Authorization: Bearer ${API_KEY}")

echo "== llama-swap / health =="
curl -fsS "${AUTH[@]}" "${BASE}/health"
echo

echo "== advertised models =="
models_json=$(curl -fsS "${AUTH[@]}" "${BASE}/v1/models")
printf '%s\n' "$models_json" | python3 -c 'import json,sys; data=json.load(sys.stdin); ids=[m.get("id") for m in data.get("data", []) if m.get("id")]; print("\n".join(f"  - {model}" for model in ids)); raise SystemExit(0 if ids else 1)'

if ! printf '%s\n' "$models_json" | MODEL="$MODEL" python3 -c 'import json,os,sys; ids={m.get("id") for m in json.load(sys.stdin).get("data", [])}; raise SystemExit(0 if os.environ["MODEL"] in ids else 1)'; then
  echo "FAIL: configured model '$MODEL' is not advertised by ${BASE}/v1/models" >&2
  exit 1
fi

echo "== chat completion =="
completion_json=$(curl -fsS "${AUTH[@]}" "${BASE}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"${MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the single word: OK\"}],\"max_tokens\":16,\"temperature\":0}")
printf '%s\n' "$completion_json" | python3 -c 'import json,sys; message=json.load(sys.stdin)["choices"][0]["message"]; text=message.get("content") or message.get("reasoning_content") or ""; print(text); raise SystemExit(0 if text.strip() else 1)'

echo "== running models =="
if ! curl -fsS "${AUTH[@]}" "${BASE}/running"; then
  echo "not exposed (the endpoint may be OpenAI-compatible but not llama-swap)"
fi
echo

echo "Self-hosted LLM check: PASS"
echo "Agent configuration:"
echo "  LLM_PROVIDER=openai-compatible"
echo "  OPENAI_BASE_URL=${BASE}/v1"
echo "  OPENAI_API_KEY=${API_KEY}"
echo "  OPENAI_MODEL=${MODEL}"
