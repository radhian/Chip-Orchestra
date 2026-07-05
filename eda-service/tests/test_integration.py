from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobs import EDAJobManager
from main import create_app
from toolchain.reports import LintReport


async def _fast_sleep(_: float) -> None:
    return None


@pytest.mark.asyncio
async def test_eda_api_integration_post_status_report_flow(tmp_path: Path) -> None:
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    manager = EDAJobManager(database_url=f"sqlite:///{tmp_path / 'eda-integration.db'}", redis_client=redis_client)
    manager.create_tables()
    app = create_app(redis_client=redis_client, manager=manager, run_worker=False)
    transport = httpx.ASGITransport(app=app)

    fake_report = LintReport(clean=True)
    fake_report.summary = "integration report"
    fake_report.metrics = {"power_mw": 12.4}

    with patch("main.uuid4", return_value="integration"), patch(
        "jobs.manager.asyncio.sleep",
        new=AsyncMock(side_effect=_fast_sleep),
    ), patch(
        "jobs.manager.run_stage",
        return_value=fake_report,
    ):
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/eda/jobs",
                json={"task_id": "task-eda", "stage": "LINT", "spec": "lint this netlist"},
            )
            assert create_response.status_code == 200
            job_id = create_response.json()["job_id"]

            await manager.process_job(job_id)

            status_response = await client.get(f"/eda/jobs/{job_id}/status")
            report_response = await client.get(f"/eda/jobs/{job_id}/report")

    assert job_id == "job-integration"
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "COMPLETED"
    report = report_response.json()
    assert report_response.status_code == 200
    assert report["summary"] == "integration report"
    assert report["metrics"] == {"power_mw": 12.4}
    assert report["stage"] == "LINT"
