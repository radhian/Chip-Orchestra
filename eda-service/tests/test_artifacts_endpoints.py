from __future__ import annotations

import sys
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobs import EDAJobManager
from main import create_app
from runner import CommandResult
from workspace import ensure_workspace


async def _fast_sleep(_: float) -> None:
    return None


class SimRunner:
    def run(self, args, *, cwd=None, timeout=None, env=None) -> CommandResult:
        arglist = [str(a) for a in args]
        prog = Path(arglist[0]).name
        if prog == "iverilog" and "-o" in arglist:
            Path(arglist[arglist.index("-o") + 1]).write_text("VVP")
            return CommandResult(args=arglist, returncode=0)
        if prog == "vvp" and cwd is not None:
            (Path(cwd) / "design.vcd").write_text("$enddefinitions $end\n#0\n")
            return CommandResult(args=arglist, returncode=0, stdout="ok")
        return CommandResult(args=arglist, returncode=0)


@pytest.mark.asyncio
async def test_artifacts_and_file_endpoints(tmp_path: Path) -> None:
    ws = ensure_workspace("task-art", tmp_path)
    (ws / "rtl" / "top.v").write_text("module top(input clk); endmodule\n")
    (ws / "tb" / "top_tb.v").write_text("module top_tb; endmodule\n")

    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    manager = EDAJobManager(
        database_url=f"sqlite:///{tmp_path / 'art.db'}",
        redis_client=redis_client,
        command_runner=SimRunner(),
    )
    manager.create_tables()
    app = create_app(redis_client=redis_client, manager=manager, run_worker=False)
    transport = httpx.ASGITransport(app=app)

    with patch("main.uuid4", return_value="art"), patch(
        "jobs.manager.asyncio.sleep", new=AsyncMock(side_effect=_fast_sleep)
    ):
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            create = await client.post(
                "/eda/jobs",
                json={
                    "task_id": "task-art",
                    "stage": "SIM",
                    "workspace_root": str(ws),
                    "top_module": "top_tb",
                },
            )
            job_id = create.json()["job_id"]
            await manager.process_job(job_id)

            artifacts_resp = await client.get(f"/eda/jobs/{job_id}/artifacts")
            file_resp = await client.get(f"/eda/jobs/{job_id}/file", params={"path": "logs/sim.log"})
            unsafe_resp = await client.get(f"/eda/jobs/{job_id}/file", params={"path": "../../etc/passwd"})
            missing_resp = await client.get(f"/eda/jobs/{job_id}/file", params={"path": "logs/nope.log"})
            not_found_job = await client.get("/eda/jobs/job-missing/artifacts")

    assert artifacts_resp.status_code == 200
    body = artifacts_resp.json()
    assert body["job_id"] == job_id
    assert body["stage"] == "SIM"
    paths = {a["path"] for a in body["artifacts"]}
    assert "logs/sim.log" in paths
    for artifact in body["artifacts"]:
        assert {"path", "kind", "stage", "size", "mime", "summary", "created_at"} <= set(artifact)

    assert file_resp.status_code == 200
    assert "iverilog" in file_resp.text

    assert unsafe_resp.status_code == 400
    assert missing_resp.status_code == 404
    assert not_found_job.status_code == 404
