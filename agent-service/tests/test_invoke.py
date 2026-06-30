from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.graph import AgentResult
from main import create_app


def test_invoke_endpoint_returns_graph_response() -> None:
    redis_client = Mock()
    redis_client.ping.return_value = True
    memory_store = Mock()
    tool_registry = Mock()
    deep_agent_graph = Mock()
    deep_agent_graph.invoke.return_value = AgentResult(
        agent_name="FlowAssistant",
        summary="FlowAssistant completed FLOW_ASSISTANT for task task-1.",
        diagnostics=[{"id": "diag-1", "title": "summary"}],
        artifacts=[{"id": "artifact-1", "name": "summary.md"}],
        workspace_files={"notes/orchestrator_patch.md": "content"},
        recommended_next="Continue DAG",
    )

    app = create_app(
        redis_client=redis_client,
        memory_store=memory_store,
        tool_registry=tool_registry,
        deep_agent_graph=deep_agent_graph,
    )

    with TestClient(app) as client:
        response = client.post(
            "/agent/invoke",
            json={
                "task_id": "task-1",
                "stage": "FLOW_ASSISTANT",
                "prompt": "Prepare orchestrator patch",
                "tools": ["write_artifact"],
                "context": {"mode": "patch"},
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "agent": "FlowAssistant",
        "summary": "FlowAssistant completed FLOW_ASSISTANT for task task-1.",
        "diagnostics": [{"id": "diag-1", "title": "summary"}],
        "artifacts": [{"id": "artifact-1", "name": "summary.md"}],
        "workspace_files": {"notes/orchestrator_patch.md": "content"},
        "recommended_next": "Continue DAG",
    }
    deep_agent_graph.invoke.assert_called_once_with(
        {
            "task_id": "task-1",
            "stage": "FLOW_ASSISTANT",
            "prompt": "Prepare orchestrator patch",
            "tools": ["write_artifact"],
            "context": {"mode": "patch"},
            "artifacts": {},
            "instructions": {},
        }
    )
