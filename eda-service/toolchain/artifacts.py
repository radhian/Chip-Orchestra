"""Artifact indexing + safe path helpers.

Provides a normalized artifact manifest (a list of dicts) plus path validation
so the ``/eda/jobs/{id}/file`` endpoint can never serve a file outside a job's
workspace. Ported/adapted from GarudaChip's ``sim.py`` ``ws_file`` guard and IP
manifest concepts.
"""
from __future__ import annotations

import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class UnsafePathError(ValueError):
    """Raised when a requested path escapes the workspace root."""


def safe_join(base: Union[str, Path], rel_path: str) -> Path:
    """Join ``rel_path`` onto ``base`` and guarantee the result stays inside base.

    Rejects absolute paths and ``..`` traversal. Returns the resolved absolute
    path (which may or may not exist yet).
    """
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


def resolve_artifact_path(base: Union[str, Path], rel_path: str) -> Path:
    """Safe-join and require the file to exist."""
    target = safe_join(base, rel_path)
    if not target.is_file():
        raise FileNotFoundError(rel_path)
    return target


def register_artifact(
    index: List[Dict[str, Any]],
    *,
    path: str,
    kind: str,
    stage: str,
    base: Optional[Union[str, Path]] = None,
    summary: str = "",
) -> Dict[str, Any]:
    """Append a normalized artifact entry to ``index`` and return it.

    Fields: ``path``, ``kind``, ``stage``, ``size``, ``mime``, ``summary``,
    ``created_at``. Duplicate paths are de-duplicated (last write wins).
    """
    size = 0
    if base is not None:
        try:
            abs_path = safe_join(base, path)
            if abs_path.is_file():
                size = abs_path.stat().st_size
        except (UnsafePathError, OSError):
            size = 0
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    entry = {
        "path": path,
        "kind": kind,
        "stage": stage,
        "size": size,
        "mime": mime,
        "summary": summary,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # de-duplicate on path
    for i, existing in enumerate(index):
        if existing.get("path") == path:
            index[i] = entry
            return entry
    index.append(entry)
    return entry


def list_artifacts(index: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return a copy of the manifest sorted by stage then path."""
    return sorted(list(index), key=lambda a: (a.get("stage", ""), a.get("path", "")))
