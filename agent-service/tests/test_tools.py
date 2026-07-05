from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import ToolRegistry


def test_update_task_status_writes_payload_to_redis() -> None:
    redis_client = Mock()
    registry = ToolRegistry(redis_client)

    result = registry.update_task_status("task-1", "PLAN", {"status": "RUNNING"})

    assert result == {"status": "updated"}
    redis_client.set.assert_called_once_with(
        "agent:task_status:task-1:PLAN",
        json.dumps({"status": "RUNNING"}),
    )


def test_track_task_progress_appends_stage_scoped_progress() -> None:
    redis_client = Mock()
    registry = ToolRegistry(redis_client)

    result = registry.track_task_progress("task-1", "RTL_GEN", {"progress": 55})

    assert result == {"status": "tracked"}
    redis_client.rpush.assert_called_once_with(
        "agent:progress:task-1",
        json.dumps({"stage": "RTL_GEN", "progress": 55}),
    )


def test_get_user_context_reads_environment_defaults() -> None:
    registry = ToolRegistry(Mock())

    with patch.dict(
        "os.environ",
        {"DEFAULT_FULL_NAME": "Test User", "DEFAULT_USERNAME": "test.user"},
        clear=False,
    ):
        result = registry.get_user_context("task-1", "PLAN", {})

    assert result == {
        "task_id": "task-1",
        "stage": "PLAN",
        "default_user": "Test User",
        "username": "test.user",
    }


def test_submit_eda_job_returns_mock_job_descriptor() -> None:
    registry = ToolRegistry(Mock())

    result = registry.submit_eda_job("task-9", "SIM", {"summary": "run sim"})

    assert result == {"job_id": "mock-task-9-sim", "status": "queued", "owner": "orchestrator"}


def test_get_eda_result_returns_mock_completion_payload() -> None:
    registry = ToolRegistry(Mock())

    result = registry.get_eda_result("task-9", "SYNTH", {})

    assert result == {
        "task_id": "task-9",
        "stage": "SYNTH",
        "status": "completed",
        "summary": "Mock EDA result",
        "owner": "orchestrator",
    }


def test_read_artifact_fetches_content_from_redis() -> None:
    redis_client = Mock()
    redis_client.get.return_value = "artifact contents"
    registry = ToolRegistry(redis_client)

    result = registry.read_artifact("task-2", "EXPORT", {"path": "reports/signoff.md"})

    assert result == "artifact contents"
    redis_client.get.assert_called_once_with("artifact:task-2:reports/signoff.md")


def test_write_artifact_persists_content_and_index() -> None:
    redis_client = Mock()
    registry = ToolRegistry(redis_client)

    result = registry.write_artifact(
        "task-3",
        "FLOW_ASSISTANT",
        {"path": "notes/orchestrator_patch.md", "content": "patched"},
    )

    assert result == {"status": "written", "path": "notes/orchestrator_patch.md"}
    redis_client.set.assert_called_once_with("artifact:task-3:notes/orchestrator_patch.md", "patched")
    redis_client.hset.assert_called_once_with("artifact:index:task-3", "notes/orchestrator_patch.md", "FLOW_ASSISTANT")
