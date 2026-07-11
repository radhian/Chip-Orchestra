"""Bundled RTL knowledge base (few-shot corpus + error-fix seed).

Curated from the GarudaChip ``data/verilog_datasets`` / ``data/knowledge_seed``
reference source. The examples are small, synthesizable modules used as
few-shot context for LLM RTL generation; ``error_fixes.json`` seeds the
auto-repair loop with known compile-error -> fix mappings.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

_KNOWLEDGE_DIR = Path(__file__).resolve().parent
_EXAMPLES_DIR = _KNOWLEDGE_DIR / "verilog_examples"
_ERROR_FIXES = _KNOWLEDGE_DIR / "error_fixes.json"


@dataclass
class VerilogExample:
    name: str
    code: str


def load_examples() -> List[VerilogExample]:
    """Return the bundled few-shot Verilog examples (sorted by name)."""
    out: List[VerilogExample] = []
    if not _EXAMPLES_DIR.is_dir():
        return out
    for path in sorted(_EXAMPLES_DIR.glob("*.*")):
        if path.suffix.lower() not in (".v", ".sv", ".vh", ".svh"):
            continue
        try:
            out.append(VerilogExample(name=path.stem, code=path.read_text(encoding="utf-8")))
        except OSError:
            continue
    return out


def load_error_fixes() -> Dict[str, str]:
    """Return the error-signature -> fix-hint seed map."""
    if not _ERROR_FIXES.is_file():
        return {}
    try:
        return json.loads(_ERROR_FIXES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def select_examples(design_hint: str, limit: int = 2) -> List[VerilogExample]:
    """Pick the most relevant few-shot examples for a design description.

    Uses cheap token overlap so it stays deterministic and dependency-free.
    Always returns at most ``limit`` examples; falls back to the first ``limit``
    when nothing overlaps.
    """
    examples = load_examples()
    if not examples:
        return []
    hint_tokens = {t for t in _tokenize(design_hint) if len(t) > 2}
    if not hint_tokens:
        return examples[:limit]
    scored = []
    for ex in examples:
        name_tokens = set(_tokenize(ex.name))
        code_tokens = set(_tokenize(ex.code[:400]))
        score = len(hint_tokens & name_tokens) * 3 + len(hint_tokens & code_tokens)
        scored.append((score, ex))
    scored.sort(key=lambda s: s[0], reverse=True)
    chosen = [ex for score, ex in scored if score > 0][:limit]
    return chosen or examples[:limit]


def lookup_fix_hints(error_text: str, limit: int = 3) -> List[str]:
    """Return fix hints whose signature substring appears in ``error_text``."""
    fixes = load_error_fixes()
    error_low = (error_text or "").lower()
    hits: List[str] = []
    for signature, hint in fixes.items():
        sig = signature.lower()
        # signature may itself be a regex-ish phrase; do a tolerant contains check
        core = sig.replace(".*", " ").split()
        if core and all(part in error_low for part in core[:4]):
            hits.append(hint)
        elif sig[:24] and sig[:24] in error_low:
            hits.append(hint)
        if len(hits) >= limit:
            break
    return hits


def _tokenize(text: str) -> List[str]:
    cleaned = "".join(c.lower() if (c.isalnum() or c == "_") else " " for c in (text or ""))
    return [t for t in cleaned.split() if t]


__all__ = [
    "VerilogExample",
    "load_examples",
    "load_error_fixes",
    "select_examples",
    "lookup_fix_hints",
]
