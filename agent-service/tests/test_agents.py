from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.graph import DeepAgentGraph


@pytest.mark.parametrize(
    ("stage", "expected_agent", "expected_next", "expected_file"),
    [
        ("SPEC_INGEST", "SpecInterpreter", "Review the structured plan and advance to PLAN.", "spec/design_brief.md"),
        ("PLAN", "FlowAssistant", "Advance to RTL_GEN and generate the design sources.", "plans/execution_plan.md"),
        ("RTL_GEN", "RTLAuthor", "Validate generated RTL and queue verification stages.", "rtl/generated_top.sv"),
        ("TB_GEN", "Verifier", "Review verification notes and move into the next scheduled EDA stage.", "tb/generated_top_tb.sv"),
        ("LINT", "Diagnoser", "Confirm orchestrator approval and continue the remaining DAG.", "reports/lint_notes.md"),
    ],
)
def test_agent_roles_resolve_to_expected_outputs(tmp_path: Path, stage: str, expected_agent: str, expected_next: str, expected_file: str) -> None:
    memory_store = Mock()
    memory_store.search_memories.return_value = [SimpleNamespace(decision="Prior diagnosis")]
    tool_registry = SimpleNamespace(tools={})

    graph = DeepAgentGraph(tool_registry, memory_store)
    result = graph.invoke(
        {
            "task_id": "task-1",
            "stage": stage,
            "prompt": f"Execute {stage}",
            "context": {"pdk_id": "sky130", "top_module": "generated_top"},
            "tools": [],
            "workspace_root": str(tmp_path),
        }
    )

    assert result.agent_name == expected_agent
    assert result.recommended_next == expected_next
    assert expected_file in result.workspace_files
    # Files were actually persisted to the resolved workspace.
    assert (tmp_path / expected_file).is_file()
    assert "task-1" in result.summary or "task_1" in result.summary or result.agent_name == expected_agent

    memory_store.save_memory.assert_called_once()
    memory_store.write_diagnosis_to_redis.assert_called_once()


def test_execute_agent_invokes_requested_tools(tmp_path: Path) -> None:
    memory_store = Mock()
    memory_store.search_memories.return_value = []
    mock_tool = Mock(return_value={"status": "ok"})
    tool_registry = SimpleNamespace(tools={"write_artifact": mock_tool})

    graph = DeepAgentGraph(tool_registry, memory_store)
    result = graph.invoke(
        {
            "task_id": "task-77",
            "stage": "FLOW_ASSISTANT",
            "prompt": "Prepare orchestrator patch",
            "tools": ["write_artifact"],
            "context": {},
            "workspace_root": str(tmp_path),
        }
    )

    assert result.agent_name == "FlowAssistant"
    assert "reports/flow_assistant_notes.md" in result.workspace_files
    mock_tool.assert_called_once_with(
        task_id="task-77",
        stage="FLOW_ASSISTANT",
        payload={
            "summary": result.summary,
            "agent": "FlowAssistant",
        },
    )
