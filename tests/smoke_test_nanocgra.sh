#!/usr/bin/env bash
# NanoCGRA-Lite end-to-end smoke test.
#
# 1. brings the full stack up (docker compose up -d)
# 2. submits the NanoCGRA-Lite prompt as a task
# 3. polls until the task reaches a terminal state
# 4. checks the expected output artifacts exist in the task workspace
# 5. prints PASS / FAIL
#
# Usage:
#   tests/smoke_test_nanocgra.sh                 # full run (starts stack)
#   NO_COMPOSE=1 tests/smoke_test_nanocgra.sh    # assume stack already up
#
# Requires: docker compose, curl, python3 (for JSON parsing).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BASE_URL="${BASE_URL:-http://localhost:${OPERATOR_PORT:-8080}}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-/tmp/chip-orchestra/workspaces}"
POLL_TIMEOUT="${POLL_TIMEOUT:-3600}"
USERNAME="${DEFAULT_USERNAME:-admin}"
PASSWORD="${DEFAULT_PASSWORD:-chip-orchestra}"

PROMPT="Design NanoCGRA-Lite: a tiny 2x2 coarse-grained reconfigurable array. \
Each processing element (PE) has a 32-bit ALU supporting pass, add, sub and \
multiply selected by a 5-bit config word, a small config register, and \
nearest-neighbour datapath connections. Provide a top module nanocgra_lite \
with clk, rst_n, a config bus, data inputs and data outputs. Target the \
GF180MCU PDK. Generate synthesizable RTL, a self-checking testbench, then take \
it through simulation, synthesis, P&R, STA, DRC/LVS and produce a GDS, a PDF \
report and visuals."

fail() { echo "SMOKE TEST: FAIL — $*"; exit 1; }
jqp()  { python3 -c "import sys,json;d=json.load(sys.stdin);print($1)" 2>/dev/null; }

if [ "${NO_COMPOSE:-0}" != "1" ]; then
  echo "[1/5] Starting stack (docker compose up -d) ..."
  docker compose up -d --build || fail "docker compose up failed"
fi

echo "[2/5] Waiting for orchestrator health at $BASE_URL/health ..."
for i in $(seq 1 60); do
  if curl -fsS "$BASE_URL/health" >/dev/null 2>&1; then break; fi
  sleep 5
  [ "$i" = "60" ] && fail "orchestrator did not become healthy"
done

# Best-effort auth: try to obtain a JWT, continue unauthenticated if the route differs.
TOKEN=""
LOGIN=$(curl -fsS -X POST "$BASE_URL/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" 2>/dev/null || true)
if [ -n "$LOGIN" ]; then
  TOKEN=$(echo "$LOGIN" | jqp "d.get('token') or d.get('access_token') or ''")
fi
AUTH=(); [ -n "$TOKEN" ] && AUTH=(-H "Authorization: Bearer $TOKEN")

echo "[3/5] Submitting NanoCGRA-Lite task ..."
CREATE=$(curl -fsS -X POST "$BASE_URL/api/tasks" "${AUTH[@]}" \
  -H 'Content-Type: application/json' \
  -d "$(python3 -c "import json,os;print(json.dumps({'name':'NanoCGRA-Lite Smoke','design_brief':os.environ['PROMPT'],'launch_mode':'FULL_FLOW_AUTO','pdk_id':'gf180mcu'}))" PROMPT="$PROMPT")" \
  ) || fail "task creation failed (check auth / API route)"
TASK_ID=$(echo "$CREATE" | jqp "d.get('task_id') or d.get('id') or ''")
[ -n "$TASK_ID" ] || fail "no task_id returned: $CREATE"
echo "      task_id = $TASK_ID"

echo "[4/5] Polling task until terminal (timeout ${POLL_TIMEOUT}s) ..."
DEADLINE=$(( $(date +%s) + POLL_TIMEOUT ))
STATUS="PENDING"
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  T=$(curl -fsS "$BASE_URL/api/tasks/$TASK_ID" "${AUTH[@]}" 2>/dev/null || true)
  STATUS=$(echo "$T" | jqp "d.get('status','')")
  STAGE=$(echo "$T" | jqp "d.get('current_stage','')")
  echo "      status=$STATUS stage=$STAGE"
  case "$STATUS" in
    COMPLETED|SUCCEEDED) break ;;
    FAILED|CANCELLED)    fail "task ended in status $STATUS at stage $STAGE" ;;
  esac
  sleep 15
done
[ "$STATUS" = "COMPLETED" ] || [ "$STATUS" = "SUCCEEDED" ] || fail "task did not complete (last status $STATUS)"

echo "[5/5] Checking expected output artifacts ..."
WS="$WORKSPACE_ROOT/$TASK_ID"
[ -d "$WS" ] || WS=$(ls -dt "$WORKSPACE_ROOT"/*/ 2>/dev/null | head -1)
[ -d "$WS" ] || fail "no task workspace found under $WORKSPACE_ROOT"
echo "      workspace = $WS"

EXPECT_ANY_RTL="$WS/rtl"
EXPECT_ANY_TB="$WS/tb"
declare -a REQUIRED=(
  "reports/final_design_report.md"
  "reports/rtl_architecture.md"
)
declare -a EXPECTED_GLOBS=(
  "$WS/rtl/*.sv:$WS/rtl/*.v"
  "$WS/tb/*_tb.sv:$WS/tb/*_tb.v"
  "$WS/waves/*.vcd"
  "$WS/gds/*.gds"
  "$WS/reports/*.png"
  "$WS/exports/final_report.pdf"
)

MISSING=0
for rel in "${REQUIRED[@]}"; do
  if [ -f "$WS/$rel" ]; then echo "      ok   $rel"; else echo "      MISS $rel"; MISSING=$((MISSING+1)); fi
done
for spec in "${EXPECTED_GLOBS[@]}"; do
  found=0
  IFS=':' read -ra alts <<< "$spec"
  for g in "${alts[@]}"; do
    if compgen -G "$g" >/dev/null; then found=1; break; fi
  done
  if [ "$found" = "1" ]; then echo "      ok   $spec"; else echo "      MISS $spec"; MISSING=$((MISSING+1)); fi
done

echo "-----------------------------------------------------"
if [ "$MISSING" -eq 0 ]; then
  echo "SMOKE TEST: PASS — NanoCGRA-Lite completed with all expected artifacts."
  exit 0
fi
echo "SMOKE TEST: FAIL — $MISSING expected artifact(s) missing."
exit 1
