from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AgentResult:
    agent_name: str
    summary: str
    diagnostics: List[Dict[str, Any]]
    artifacts: List[Dict[str, Any]]
    workspace_files: Dict[str, str]
    recommended_next: str
    # New optional structured fields (backwards compatible with existing response
    # shape — main.py only serializes the original six fields).
    structured_conclusion: Dict[str, Any] = field(default_factory=dict)
    artifact_refs: List[str] = field(default_factory=list)
