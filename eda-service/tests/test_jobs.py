from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import create_app


@pytest.mark.asyncio
async def test_job_endpoint_crud_handlers() -> None:
    redis_client = AsyncMock()
    manager = Mock()
    manager.enqueue_job = AsyncMock()

    job = SimpleNamespace(
        id="job-fixed",
        status="COMPLETED",
        stage="SIM",
        progress=100,
        report_json='{"summary":"done"}',
        error="",
        updated_at=datetime(2024, 1, 1, 12, 0, 0),
    )
    manager.get_job.side_effect = [job, job, job, None]
    manager.delete_job.side_effect = [True, False]

    app = create_app(redis_client=redis_client, manager=manager, run_worker=False)
    transport = httpx.ASGITransport(app=app)

    with patch("main.uuid4", return_value="fixed"):
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/eda/jobs",
                json={"task_id": "task-1", "stage": "SIM", "spec": "run sim"},
            )
            status_response = await client.get("/eda/jobs/job-fixed/status")
            report_response = await client.get("/eda/jobs/job-fixed/report")
            delete_response = await client.delete("/eda/jobs/job-fixed")
            missing_delete_response = await client.delete("/eda/jobs/job-fixed")

    assert create_response.status_code == 200
    assert create_response.json() == {
        "job_id": "job-fixed",
        "status": "QUEUED",
        "message": "SIM job accepted",
    }
    manager.create_job.assert_called_once_with(
        job_id="job-fixed",
        task_id="task-1",
        stage="SIM",
        workspace_root="",
        stage_options={
            "top_module": "",
            "clock_port": "clk",
            "clock_period": 10.0,
            "stage_options": {},
            "spec": "run sim",
            "metadata": {},
        },
        artifacts={},
    )
    manager.enqueue_job.assert_awaited_once_with("job-fixed")

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "COMPLETED"
    assert status_response.json()["report"] == {"summary": "done"}

    assert report_response.status_code == 200
    assert report_response.json() == {"summary": "done"}

    assert delete_response.status_code == 200
    assert delete_response.json() == {"status": "deleted", "job_id": "job-fixed"}

    assert missing_delete_response.status_code == 404
    assert missing_delete_response.json() == {"detail": "Job not found"}
