#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Verify the self-hosted server is up and answering OpenAI-style requests.
# Point it at wherever the server listens (default localhost:8000).
#
#   ./healthcheck.sh                       # localhost:8000
#   BASE=http://gpu-node:8000 ./healthcheck.sh
# ---------------------------------------------------------------------------
set -uo pipefail
BASE="${BASE:-http://localhost:${LLM_SERVE_PORT:-8000}}"
MODEL="${OPENAI_MODEL:-Qwen3.8-27B-multimodal}"

echo "== /v1/models @ $BASE =="
if ! curl -fsS "$BASE/v1/models" | head -c 600; then
  echo; echo "FAIL: server not reachable / not ready at $BASE"; exit 1
fi
echo; echo

echo "== chat completion smoke test =="
curl -fsS "$BASE/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer EMPTY" \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the single word: OK\"}],\"max_tokens\":16,\"temperature\":0}" \
  | head -c 1200
echo; echo
echo ">> If you see a JSON completion above, wire agent-service:"
echo "   LLM_PROVIDER=openai-compatible  OPENAI_BASE_URL=$BASE/v1  OPENAI_API_KEY=EMPTY  OPENAI_MODEL=$MODEL"
