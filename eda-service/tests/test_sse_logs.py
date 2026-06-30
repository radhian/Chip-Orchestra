from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import fakeredis.aioredis
import pytest
from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobs import EDAJobManager
from main import create_app


@pytest.mark.asyncio
async def test_sse_log_stream_returns_existing_log_lines(tmp_path: Path) -> None:
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    manager = EDAJobManager(database_url=f"sqlite:///{tmp_path / 'eda-sse.db'}", redis_client=redis_client)
    manager.create_tables()
    manager.create_job(job_id="job-stream", task_id="task-1", stage="SIM")
    await manager.append_log("job-stream", "Seed log line")

    app = create_app(redis_client=redis_client, manager=manager, run_worker=False)
    route = next(route for route in app.router.routes if getattr(route, "path", "") == "/eda/jobs/{job_id}/logs")
    scope = {"type": "http", "method": "GET", "path": "/eda/jobs/job-stream/logs", "headers": [], "app": app}
    request = Request(scope)

    response = await route.endpoint("job-stream", request)
    assert response.media_type == "text/event-stream"

    first_chunk = await response.body_iterator.__anext__()
    assert "Seed log line" in first_chunk

    await response.body_iterator.aclose()
    await redis_client.aclose()
