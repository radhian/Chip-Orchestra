#!/usr/bin/env python3
"""Deprecated: project-authored geometric dummy fill is forbidden."""
import sys

sys.stderr.write(
    "ERROR: add_density_fill.py is deprecated and intentionally does not write GDS.\n"
    "The canonical GDS must remain free of project-generated dummy-purpose shapes.\n"
    "Use only foundry-approved density-fill tooling outside this canonical flow, and\n"
    "keep any resulting review artifact separate from nanocgra_lite_3x3_opt.gds.\n"
)
raise SystemExit(2)
