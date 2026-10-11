#!/usr/bin/env bash
set -eu
export PYTHONPATH=/mnt/d/LinkedinProjects/Chip-Orchestra/paper/eda_runtime
export PATH=/home/wlmoi/venvs/librelane/bin:/home/wlmoi/.nix-profile/bin:/usr/bin:/bin
export PDK_ROOT=/home/wlmoi/.volare
export PDK=gf180mcuD
export LIBRELANE_PATH=/home/wlmoi/venvs/librelane/bin/librelane
export EDA_JOB_TIMEOUT_HARDEN=3600
export _LLN_OVERRIDE_YOSYS=/mnt/d/LinkedinProjects/Chip-Orchestra/paper/yosys-python.sh
export MPLCONFIGDIR=/mnt/d/LinkedinProjects/Chip-Orchestra/paper/eda_runtime/mplconfig
/home/wlmoi/venvs/librelane/bin/python /mnt/d/LinkedinProjects/Chip-Orchestra/paper/run_nanocgra_e2e.py > /mnt/d/LinkedinProjects/Chip-Orchestra/paper/nanocgra_e2e_20261011/execution.log 2>&1
