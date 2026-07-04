from __future__ import annotations

import asyncio
import contextlib
import json
import os
from contextlib import asynccontextmanager
from typing import Any, Dict
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from jobs import EDAJobManager
from toolchain.artifacts import UnsafePathError, list_artifacts, resolve_artifact_path
from workspace import resolve_workspace


class CreateEDAJobRequest(BaseModel):
    task_id: str
    stage: str
    spec: str = Field(default="")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    artifacts: Dict[str, str] = Field(default_factory=dict)
    # New optional fields (backwards compatible). Top-level values win over
    # equivalent keys nested under ``metadata``.
    workspace_root: str | None = None
    top_module: str | None = None
    clock_port: str | None = None
    clock_period: float | None = None
    stage_options: Dict[str, Any] = Field(default_factory=dict)

    def resolved_workspace_root(self) -> str:
        return self.workspace_root or str(self.metadata.get("workspace_root") or "")

    def build_options(self) -> Dict[str, Any]:
        meta = self.metadata or {}
        return {
            "top_module": self.top_module or meta.get("top_module") or meta.get("top") or "",
            "clock_port": self.clock_port or meta.get("clock_port") or "clk",
            "clock_period": self.clock_period if self.clock_period is not None else meta.get("clock_period", 10.0),
            "stage_options": self.stage_options or meta.get("stage_options") or {},
            "spec": self.spec,
            "metadata": meta,
        }


def build_services():
    database_url = os.getenv("DATABASE_URL", "mysql+pymysql://chip:chip@mysql:3306/chip_orchestra")
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    redis_client = Redis.from_url(redis_url, decode_responses=True)
    manager = EDAJobManager(database_url=database_url, redis_client=redis_client)
    manager.create_tables()
    return redis_client, manager


def _assign_services(app: FastAPI, redis_client: Redis, manager: EDAJobManager):
    app.state.redis_client = redis_client
    app.state.manager = manager


def create_app(*, redis_client: Redis | None = None, manager: EDAJobManager | None = None, run_worker: bool = True) -> FastAPI:
    if (redis_client is None) != (manager is None):
        raise ValueError("redis_client and manager must be provided together")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not hasattr(app.state, "manager"):
            built_redis, built_manager = build_services()
            _assign_services(app, built_redis, built_manager)
        worker = None
        if run_worker:
            worker = asyncio.create_task(app.state.manager.worker_loop())
        try:
            yield
        finally:
            if worker is not None:
                worker.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await worker
            close = getattr(app.state.redis_client, "aclose", None)
            if callable(close):
                await close()

    app = FastAPI(title="Chip Orchestra EDA Service", version="0.1.0", lifespan=lifespan)
    if redis_client is not None and manager is not None:
        _assign_services(app, redis_client, manager)

    @app.get("/health")
    async def health(request: Request):
        return {"status": "ok", "redis": await request.app.state.redis_client.ping()}

    @app.post("/eda/jobs")
    async def create_job(request: CreateEDAJobRequest, fastapi_request: Request):
        job_id = f"job-{uuid4()}"
        fastapi_request.app.state.manager.create_job(
            job_id=job_id,
            task_id=request.task_id,
            stage=request.stage,
            workspace_root=request.resolved_workspace_root(),
            stage_options=request.build_options(),
            artifacts=request.artifacts,
        )
        await fastapi_request.app.state.manager.enqueue_job(job_id)
        return {"job_id": job_id, "status": "QUEUED", "message": f"{request.stage} job accepted"}

    @app.get("/eda/jobs/{job_id}/status")
    async def get_job_status(job_id: str, request: Request):
        job = request.app.state.manager.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "job_id": job.id,
            "status": job.status,
            "stage": job.stage,
            "progress": job.progress,
            "report": json.loads(job.report_json or "{}"),
            "error": job.error,
            "updated_at": job.updated_at.isoformat() + "Z",
        }

    @app.get("/eda/jobs/{job_id}/report")
    async def get_job_report(job_id: str, request: Request):
        job = request.app.state.manager.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return json.loads(job.report_json or "{}")

    @app.get("/eda/jobs/{job_id}/artifacts")
    async def get_job_artifacts(job_id: str, request: Request):
        job = request.app.state.manager.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        artifacts = list_artifacts(json.loads(job.artifact_index or "[]"))
        return {"job_id": job.id, "task_id": job.task_id, "stage": job.stage, "artifacts": artifacts}

    @app.get("/eda/jobs/{job_id}/file")
    async def get_job_file(job_id: str, path: str, request: Request):
        job = request.app.state.manager.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        workspace = resolve_workspace(job.task_id, job.workspace_root)
        try:
            target = resolve_artifact_path(workspace, path)
        except UnsafePathError:
            raise HTTPException(status_code=400, detail="Invalid path")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(str(target))

    @app.get("/eda/jobs/{job_id}/logs")
    async def stream_job_logs(job_id: str, request: Request):
        manager = request.app.state.manager
        redis_client = request.app.state.redis_client
        if manager.get_job(job_id) is None:
            raise HTTPException(status_code=404, detail="Job not found")

        async def event_stream():
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(f"eda:job:{job_id}:status")
            existing = await redis_client.lrange(f"eda:job:{job_id}:logs", 0, -1)
            for line in existing:
                yield f"data: {line}\n\n"
            try:
                while True:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message and message.get("data"):
                        yield f"data: {message['data']}\n\n"
                    await asyncio.sleep(0.2)
            finally:
                await pubsub.unsubscribe(f"eda:job:{job_id}:status")
                await pubsub.close()

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.delete("/eda/jobs/{job_id}")
    async def delete_job(job_id: str, request: Request):
        deleted = request.app.state.manager.delete_job(job_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"status": "deleted", "job_id": job_id}

    return app


app = create_app()
