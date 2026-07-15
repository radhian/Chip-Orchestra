"""Durable error→fix lesson store (GarudaChip's pg/MinIO knowledge DB, adapted).

GarudaChip persists every broken→clean Verilog transition as a 'fix' lesson in
Postgres+MinIO. The agent service keeps the same behaviour with a lighter
backend: a JSON file on the shared workspace volume, so lessons survive across
tasks and container restarts. Every debug point (compile-on-write in the deep
agent's ``write_file_disk``, the repair loop) funnels through
:func:`remember_fix`; recall happens at the start of every correction and via
the ``recall_memory`` agent tool.

Recall is deliberately dependency-free (token overlap on the error signature)
and merges the bundled ``knowledge/error_fixes.json`` seed so the store is
never empty.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from pathlib import Path
from typing import Dict, List

_LOCK = threading.Lock()


def _store_path() -> Path:
    root = os.getenv("AGENT_ARTIFACT_ROOT", os.getenv("WORKSPACE_ROOT", "/tmp/chip-orchestra/workspaces"))
    return Path(root) / ".knowledge" / "fix_lessons.json"


def _load() -> Dict[str, dict]:
    p = _store_path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data: Dict[str, dict]) -> None:
    p = _store_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=1), encoding="utf-8")
    except OSError:
        pass


def error_signature(err: str) -> str:
    """Concise signature = the first real error message line, paths/line numbers
    stripped, so the same mistake dedupes to one lesson."""
    sigline = next((ln for ln in (err or "").splitlines()
                    if "error" in ln.lower() or "warning" in ln.lower()), (err or "")[:80])
    return re.sub(r"^.*?:\s*\d+:?\s*", "", sigline).strip()[:120] or "verilog error"


def remember_fix(error_sig: str, hint: str = "", *, design: str = "", broken: str = "",
                 fixed: str = "") -> None:
    """Persist an error→fix lesson. Saved AUTOMATICALLY at every debug point;
    deduped by the error signature so the same lesson isn't stored twice.
    Optionally include the BROKEN and FIXED code for a concrete before/after."""
    if not error_sig:
        return
    body = f"ERROR SIGNATURE: {error_sig}\n\n"
    if broken:
        body += f"BROKEN (do NOT write this):\n```verilog\n{broken[:1500]}\n```\n\n"
    if fixed:
        body += f"CORRECT FIX:\n```verilog\n{fixed[:2000]}\n```\n\n"
    if hint and not fixed:
        body += f"FIX: {hint}\n"
    rid = "fix_" + hashlib.sha1(error_sig.lower().encode()).hexdigest()[:16]
    with _LOCK:
        data = _load()
        data[rid] = {"sig": error_sig[:300], "design": design, "text": body}
        _save(data)


def _tokens(text: str) -> set:
    return {t for t in re.findall(r"[a-z0-9_]{3,}", (text or "").lower())}


def recall_fix(error_sig: str) -> str:
    """Best-matching past fix lesson for an error signature/topic ('' if none).
    Token-overlap match over the stored lessons, then the bundled seed map."""
    query = _tokens(error_sig)
    if not query:
        return ""
    best, best_score = "", 0
    with _LOCK:
        data = _load()
    for item in data.values():
        score = len(query & _tokens(item.get("sig", "") + " " + item.get("text", "")[:300]))
        if score > best_score:
            best, best_score = item.get("text", ""), score
    if best and best_score >= 2:
        return best
    # fall back to the bundled error-fix seed
    try:
        import knowledge
        hits: List[str] = knowledge.lookup_fix_hints(error_sig, limit=1)
        if hits:
            return f"SEED FIX HINT: {hits[0]}"
    except Exception:  # noqa: BLE001
        pass
    return ""


__all__ = ["remember_fix", "recall_fix", "error_signature"]
