from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobs import EDAJobManager
from toolchain.reports import SimReport


async def _fast_sleep(_: float) -> None:
    return None


@pytest.mark.asyncio
async def test_process_job_transitions_from_queued_to_completed(tmp_path: Path) -> None:
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    manager = EDAJobManager(database_url=f"sqlite:///{tmp_path / 'eda-complete.db'}", redis_client=redis_client)
    manager.create_tables()
    manager.create_job(job_id="job-1", task_id="task-1", stage="SIM")

    fake_report = SimReport(top="uart_top", compiled=True, waveform=True)
    fake_report.summary = "toolchain finished"
    fake_report.metrics = {"timing_slack_ns": 0.11}
    fake_report.artifacts = [{"path": "waves/design.vcd", "kind": "waveform", "stage": "SIM"}]

    with patch("jobs.manager.asyncio.sleep", new=AsyncMock(side_effect=_fast_sleep)), patch(
        "jobs.manager.run_stage",
        return_value=fake_report,
    ):
        await manager.process_job("job-1")

    job = manager.get_job("job-1")
    assert job is not None
    assert job.status == "COMPLETED"
    assert job.progress == 100
    assert "toolchain finished" in job.report_json
    assert "waves/design.vcd" in job.artifact_index

    logs = await redis_client.lrange("eda:job:job-1:logs", 0, -1)
    assert any("Starting SIM stage" in line for line in logs)
    assert any("SIM stage completed" in line for line in logs)


@pytest.mark.asyncio
async def test_process_job_transitions_from_queued_to_failed(tmp_path: Path) -> None:
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    manager = EDAJobManager(database_url=f"sqlite:///{tmp_path / 'eda-fail.db'}", redis_client=redis_client)
    manager.create_tables()
    manager.create_job(job_id="job-2", task_id="task-2", stage="SYNTH")

    with patch("jobs.manager.asyncio.sleep", new=AsyncMock(side_effect=_fast_sleep)), patch(
        "jobs.manager.run_stage",
        side_effect=RuntimeError("toolchain exploded"),
    ):
        await manager.process_job("job-2")

    job = manager.get_job("job-2")
    assert job is not None
    assert job.status == "FAILED"
    assert job.progress == 100
    assert job.error == "toolchain exploded"

    logs = await redis_client.lrange("eda:job:job-2:logs", 0, -1)
    assert any("Job failed: toolchain exploded" in line for line in logs)


@pytest.mark.asyncio
async def test_a_stage_that_reported_errors_is_not_completed(tmp_path: Path) -> None:
    """A runner that returns normally but recorded hard errors has NOT done its
    job. Reporting COMPLETED let the flow march past a hardening run that timed
    out and produced no GDS — the run could then reach EXPORT with no layout."""
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    manager = EDAJobManager(database_url=f"sqlite:///{tmp_path / 'eda-errs.db'}",
                            redis_client=redis_client)
    manager.create_tables()
    manager.create_job(job_id="job-3", task_id="task-3", stage="SYNTH")

    fake_report = SimReport(top="nano_cgra_sobel_top")
    fake_report.summary = "LibreLane hardening did not produce a GDS."
    fake_report.errors = ["hardening timeout", "no GDS produced"]

    with patch("jobs.manager.asyncio.sleep", new=AsyncMock(side_effect=_fast_sleep)), patch(
        "jobs.manager.run_stage", return_value=fake_report,
    ):
        await manager.process_job("job-3")

    job = manager.get_job("job-3")
    assert job is not None
    assert job.status == "FAILED"
    assert "hardening timeout" in job.error
    # The report must still be persisted — that is where the reason lives.
    assert "did not produce a GDS" in job.report_json

    logs = await redis_client.lrange("eda:job:job-3:logs", 0, -1)
    assert any("SYNTH stage failed" in line for line in logs)


@pytest.mark.asyncio
async def test_warnings_alone_do_not_fail_a_stage(tmp_path: Path) -> None:
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    manager = EDAJobManager(database_url=f"sqlite:///{tmp_path / 'eda-warn.db'}",
                            redis_client=redis_client)
    manager.create_tables()
    manager.create_job(job_id="job-4", task_id="task-4", stage="SYNTH")

    fake_report = SimReport(top="nano_cgra_sobel_top")
    fake_report.summary = "hardened"
    fake_report.warnings = ["requested top module ... is not declared in rtl/"]

    with patch("jobs.manager.asyncio.sleep", new=AsyncMock(side_effect=_fast_sleep)), patch(
        "jobs.manager.run_stage", return_value=fake_report,
    ):
        await manager.process_job("job-4")

    job = manager.get_job("job-4")
    assert job is not None
    assert job.status == "COMPLETED"
