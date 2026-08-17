#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Pre-flight checks for the AMD GPU node before serving GLM-5.2.
# Confirms ROCm, GPU count, HBM, disk headroom, and Docker device access.
# ---------------------------------------------------------------------------
set -uo pipefail

HW_PROFILE="${HW_PROFILE:-mi300x}"
HF_CACHE_DIR="${HF_CACHE_DIR:-/data/hf-cache}"

case "$HW_PROFILE" in
  mi300x|mi325x)   NEED_GPUS=8 ;;
  mi355x-fp8|mi355x-fp4) NEED_GPUS=4 ;;
  *) NEED_GPUS=8 ;;
esac

fail=0
note() { printf '  %-8s %s\n' "$1" "$2"; }

echo "== ROCm =="
if command -v rocm-smi >/dev/null 2>&1; then
  GPU_COUNT=$(rocm-smi --showid 2>/dev/null | grep -c '^GPU' || echo 0)
  note "[ok]" "rocm-smi present; detected GPUs: ${GPU_COUNT}"
  if [ "${GPU_COUNT:-0}" -lt "$NEED_GPUS" ]; then
    note "[warn]" "profile $HW_PROFILE expects >= $NEED_GPUS GPUs"; fail=1
  fi
  rocm-smi --showmeminfo vram 2>/dev/null | grep -i 'total' | head -1
else
  note "[FAIL]" "rocm-smi not found — install ROCm >= 6.2 (7.2.x recommended)"; fail=1
fi

echo "== Docker device access =="
if command -v docker >/dev/null 2>&1; then
  note "[ok]" "docker present"
  [ -e /dev/kfd ] && note "[ok]" "/dev/kfd exists" || { note "[FAIL]" "/dev/kfd missing"; fail=1; }
  [ -e /dev/dri ] && note "[ok]" "/dev/dri exists" || { note "[FAIL]" "/dev/dri missing"; fail=1; }
else
  note "[FAIL]" "docker not found"; fail=1
fi

echo "== Disk (weights cache) =="
mkdir -p "$HF_CACHE_DIR" 2>/dev/null || true
AVAIL_GB=$(df -PBG "$HF_CACHE_DIR" 2>/dev/null | awk 'NR==2{gsub("G","",$4);print $4}')
note "[info]" "free at $HF_CACHE_DIR: ${AVAIL_GB:-?} GB (need ~800GB for FP8, ~400GB for MXFP4)"
if [ "${AVAIL_GB:-0}" -lt 400 ]; then note "[warn]" "low disk for model weights"; fail=1; fi

echo
[ "$fail" -eq 0 ] && echo "PRE-FLIGHT: PASS" || echo "PRE-FLIGHT: issues found (see [FAIL]/[warn] above)"
exit "$fail"
