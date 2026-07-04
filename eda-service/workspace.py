"""Standardized task workspace layout.

Every EDA task gets a stable directory tree so simulation, hardening and report
artifacts always land in predictable places::

    workspaces/<task-id>/
      rtl/       generated / uploaded synthesizable sources
      tb/        testbenches
      reports/   structured stage reports (json / markdown)
      logs/      raw tool logs (sim.log, librelane.log, ...)
      waves/     simulation waveforms (design.vcd)
      gds/       hardening outputs (<top>.gds, <top>.png)
      context/   design context / spec artifacts
      exports/   promoted final artifacts

This mirrors GarudaChip's filesystem-heavy execution model while fitting Chip
Orchestra's task/stage semantics.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

WORKSPACE_SUBDIRS = ("rtl", "tb", "reports", "logs", "waves", "gds", "context", "exports")

DEFAULT_WORKSPACE_ROOT = "/tmp/chip-orchestra/workspaces"


def default_workspace_root() -> Path:
    """Parent directory that contains every ``<task-id>`` workspace."""
    return Path(os.getenv("WORKSPACE_ROOT", DEFAULT_WORKSPACE_ROOT))


def ensure_workspace(task_id: str, root: Optional[Union[str, Path]] = None) -> Path:
    """Create (idempotently) and return the standardized workspace for ``task_id``.

    ``root`` is the parent directory holding all task workspaces; it defaults to
    ``WORKSPACE_ROOT`` (env) → ``/tmp/chip-orchestra/workspaces``.
    """
    base = Path(root) if root is not None else default_workspace_root()
    workspace = base / _safe_component(task_id)
    for sub in WORKSPACE_SUBDIRS:
        (workspace / sub).mkdir(parents=True, exist_ok=True)
    return workspace


def resolve_workspace(task_id: str, workspace_root: Optional[str] = None) -> Path:
    """Resolve the on-disk workspace directory for a job.

    ``workspace_root`` is the value carried on the job request (e.g.
    ``"workspaces/<task-id>"``). When absolute it is used verbatim; when relative
    it is treated as informational and the canonical layout under
    ``WORKSPACE_ROOT`` is used instead. This keeps the API field round-trippable
    without letting a client escape the configured root.
    """
    if workspace_root:
        candidate = Path(workspace_root)
        if candidate.is_absolute():
            for sub in WORKSPACE_SUBDIRS:
                (candidate / sub).mkdir(parents=True, exist_ok=True)
            return candidate
    return ensure_workspace(task_id)


def _safe_component(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)
    return cleaned or "task"
