from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional

from redis.asyncio import Redis
from sqlalchemy import DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from toolchain import run_mock_toolchain


class Base(DeclarativeBase):
    pass


class EDAJob(Base):
    __tablename__ = "eda_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    stage: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    report_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EDAJobManager:
    def __init__(self, database_url: str, redis_client: Redis):
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.redis = redis_client

    def create_tables(self):
        Base.metadata.create_all(self.engine)

    def create_job(self, job_id: str, task_id: str, stage: str):
        with self.Session() as session:
            job = EDAJob(id=job_id, task_id=task_id, stage=stage, status="QUEUED", progress=0)
            session.add(job)
            session.commit()
        return job

    def get_job(self, job_id: str) -> Optional[EDAJob]:
        with Session(self.engine) as session:
            stmt = select(EDAJob).where(EDAJob.id == job_id)
            return session.execute(stmt).scalar_one_or_none()

    def delete_job(self, job_id: str):
        with self.Session() as session:
            row = session.get(EDAJob, job_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    async def enqueue_job(self, job_id: str):
        await self.redis.rpush("eda:jobs:queue", job_id)
        await self.append_log(job_id, "Job queued")

    async def append_log(self, job_id: str, line: str):
        await self.redis.rpush(f"eda:job:{job_id}:logs", f"{datetime.utcnow().isoformat()}Z {line}")

    async def worker_loop(self):
        while True:
            item = await self.redis.blpop("eda:jobs:queue", timeout=1)
            if not item:
                await asyncio.sleep(0.2)
                continue
            _, job_id = item
            await self.process_job(job_id)

    async def process_job(self, job_id: str):
        with self.Session() as session:
            job = session.get(EDAJob, job_id)
            if job is None:
                return
            job.status = "RUNNING"
            job.progress = 10
            session.commit()
        await self.append_log(job_id, "Starting mock toolchain")
        await self.redis.publish(f"eda:job:{job_id}:status", json.dumps({"job_id": job_id, "status": "RUNNING", "progress": 10}))

        try:
            for progress in (25, 55, 80):
                await asyncio.sleep(1)
                self._update_progress(job_id, progress)
                await self.append_log(job_id, f"Progress updated to {progress}%")
                await self.redis.publish(f"eda:job:{job_id}:status", json.dumps({"job_id": job_id, "status": "RUNNING", "progress": progress}))

            job = self.get_job(job_id)
            if job is None:
                return
            report = await run_mock_toolchain(job.stage, job.task_id)
            with self.Session() as session:
                row = session.get(EDAJob, job_id)
                if row is None:
                    return
                row.status = "COMPLETED"
                row.progress = 100
                row.report_json = json.dumps(report)
                session.commit()
            await self.append_log(job_id, "Mock toolchain completed")
            await self.redis.publish(f"eda:job:{job_id}:status", json.dumps({"job_id": job_id, "status": "COMPLETED", "progress": 100, "report": report}))
        except Exception as exc:  # pragma: no cover - defensive path
            with self.Session() as session:
                row = session.get(EDAJob, job_id)
                if row is None:
                    return
                row.status = "FAILED"
                row.error = str(exc)
                row.progress = 100
                session.commit()
            await self.append_log(job_id, f"Job failed: {exc}")
            await self.redis.publish(f"eda:job:{job_id}:status", json.dumps({"job_id": job_id, "status": "FAILED", "progress": 100, "error": str(exc)}))

    def _update_progress(self, job_id: str, progress: int):
        with self.Session() as session:
            row = session.get(EDAJob, job_id)
            if row is None:
                return
            row.progress = progress
            row.updated_at = datetime.utcnow()
            session.commit()
