"""Agent-side workspace/file helpers.

The agent service reads reference/spec/EDA artifacts and writes generated RTL,
testbenches and reports into the same standardized task workspace layout used by
the EDA service. The small layout constants are intentionally duplicated here
(rather than shared via a package) so each service keeps its own Docker image.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Union

WORKSPACE_SUBDIRS = ("rtl", "tb", "reports", "logs", "waves", "gds", "context", "exports", "spec", "plans")

DEFAULT_ARTIFACT_ROOT = "/tmp/chip-orchestra/workspaces"


class UnsafePathError(ValueError):
    """Raised when a path escapes the workspace root."""


def artifact_root() -> Path:
    return Path(os.getenv("AGENT_ARTIFACT_ROOT", os.getenv("WORKSPACE_ROOT", DEFAULT_ARTIFACT_ROOT)))


def _safe_component(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)
    return cleaned or "task"


def ensure_workspace(task_id: str, root: Optional[Union[str, Path]] = None) -> Path:
    base = Path(root) if root is not None else artifact_root()
    workspace = base / _safe_component(task_id)
    for sub in WORKSPACE_SUBDIRS:
        (workspace / sub).mkdir(parents=True, exist_ok=True)
    return workspace


def resolve_workspace(task_id: str, workspace_root: Optional[str] = None) -> Path:
    if workspace_root:
        candidate = Path(workspace_root)
        if candidate.is_absolute():
            for sub in WORKSPACE_SUBDIRS:
                (candidate / sub).mkdir(parents=True, exist_ok=True)
            return candidate
    return ensure_workspace(task_id)


def safe_join(base: Union[str, Path], rel_path: str) -> Path:
    base_resolved = Path(base).resolve()
    if not rel_path:
        raise UnsafePathError("empty path")
    candidate = Path(rel_path)
    if candidate.is_absolute():
        raise UnsafePathError("absolute paths are not allowed")
    target = (base_resolved / candidate).resolve()
    if target != base_resolved and base_resolved not in target.parents:
        raise UnsafePathError("path escapes workspace")
    return target


def write_file(base: Union[str, Path], rel_path: str, content: str) -> Path:
    target = safe_join(base, rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return target


def read_file(base: Union[str, Path], rel_path: str) -> str:
    target = safe_join(base, rel_path)
    if not target.is_file():
        raise FileNotFoundError(rel_path)
    return target.read_text(errors="replace")


def list_files(base: Union[str, Path]) -> List[str]:
    base_resolved = Path(base).resolve()
    if not base_resolved.is_dir():
        return []
    out: List[str] = []
    for p in sorted(base_resolved.rglob("*")):
        if p.is_file():
            out.append(str(p.relative_to(base_resolved)))
    return out


def persist_workspace_files(base: Union[str, Path], files: Dict[str, str]) -> None:
    for rel_path, content in files.items():
        try:
            write_file(base, rel_path, content)
        except UnsafePathError:
            continue
