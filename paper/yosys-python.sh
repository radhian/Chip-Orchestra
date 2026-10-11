#!/usr/bin/env bash
if [ "${1:-}" = "-y" ]; then
  shift
  script="$1"
  shift
  if [ "${1:-}" = "--" ]; then shift; fi
  exec /home/wlmoi/venvs/librelane/bin/python "$script" "$@"
fi
exec /home/wlmoi/.nix-profile/bin/yosys "$@"
