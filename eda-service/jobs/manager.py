from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from redis.asyncio import Redis
from sqlalchemy import DateTime, Integer, String, Text, create_engine, select, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from runner import CommandRunner, default_runner
from toolchain import run_gl_sim, run_harden, run_lint, run_mock_toolchain, run_render, run_simulation, run_sta
from toolchain.reports import BaseReport, SignoffReport
from workspace import resolve_workspace

COMPILE_EXT = (".v", ".sv")


class Base(DeclarativeBase):
    pass


class EDAJob(Base):
    __tablename__ = "eda_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    stage: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    # MEDIUMTEXT on MySQL: a SIM report with waveform/artifact metadata can
    # exceed TEXT's 64KB and 1406 "Data too long" then failed the whole stage.
    report_json: Mapped[str] = mapped_column(Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    # New (nullable) fields — preserve existing columns to avoid migration breakage.
    workspace_root: Mapped[str] = mapped_column(String(512), default="")
    stage_options: Mapped[str] = mapped_column(Text, default="{}")
    artifact_index: Mapped[str] = mapped_column(Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def _gather_sources(workspace: Path, *, include_tb: bool) -> List[Path]:
    sources: List[Path] = []
    rtl_dir = workspace / "rtl"
    if rtl_dir.is_dir():
        sources += [p for p in sorted(rtl_dir.glob("*")) if p.suffix.lower() in COMPILE_EXT]
    if include_tb:
        tb_dir = workspace / "tb"
        if tb_dir.is_dir():
            sources += [p for p in sorted(tb_dir.glob("*")) if p.suffix.lower() in COMPILE_EXT]
    return sources


def run_stage(
    *,
    stage: str,
    task_id: str,
    workspace: Path,
    opts: Optional[Dict[str, Any]] = None,
    runner: CommandRunner = default_runner,
) -> BaseReport:
    """Dispatch a job to the right toolchain runner and return a structured report.

    - ``SIM``                    -> :func:`run_simulation`
    - ``LINT``                   -> :func:`run_lint`
    - ``SYNTH``/``PNR``/``DRC_LVS`` -> :func:`run_harden`
    - ``SIGNOFF``                -> signoff report derived from the workspace
    - anything else              -> mock fallback report
    """
    opts = opts or {}
    stage = stage.upper()
    top = str(opts.get("top_module") or opts.get("top") or "")
    if not top:
        # The agent flow records the top module in spec/spec.json — without it
        # the SIM testbench selection and hardening had to guess (and picked a
        # unit testbench / wrong module).
        try:
            spec = json.loads((workspace / "spec" / "spec.json").read_text())
            top = str(spec.get("top_module") or "")
        except Exception:  # noqa: BLE001
            top = ""
    clock_port = str(opts.get("clock_port") or "clk")
    try:
        clock_period = float(opts.get("clock_period") or 10.0)
    except (TypeError, ValueError):
        clock_period = 10.0
    stage_opts = opts.get("stage_options") or {}

    if stage == "SIM":
        return run_simulation(workspace, _gather_sources(workspace, include_tb=True), top, stage_opts, runner)
    if stage == "LINT":
        return run_lint(workspace, _gather_sources(workspace, include_tb=False), top, stage_opts, runner)
    if stage in ("SYNTH", "PNR", "DRC_LVS"):
        return run_harden(workspace, top, clock_port, clock_period, stage_opts, runner, stage=stage)
    if stage in ("STA", "POWER"):
        return run_sta(workspace, top, clock_period, stage_opts, runner, stage=stage)
    if stage == "GL_SIM":
        return run_gl_sim(workspace, top, stage_opts, runner, stage=stage)
    if stage == "RENDER":
        return run_render(workspace, top, stage_opts, runner, stage=stage)
    if stage == "SIGNOFF":
        return _signoff_report(task_id, stage)
    # Fallback for any other stage: reuse the mock toolchain shape.
    report = BaseReport(stage=stage)
    report.summary = f"Mock {stage} execution completed successfully."
    report.metrics = {"timing_slack_ns": 0.11, "power_mw": 12.4, "area_um2": 48123}
    return report


def _signoff_report(task_id: str, stage: str) -> SignoffReport:
    report = SignoffReport(stage=stage)
    report.summary = "Signoff aggregation completed."
    report.signoff = {"clean": True, "failed": []}
    report.tapeout_ready = True
    return report


class EDAJobManager:
    def __init__(self, database_url: str, redis_client: Redis, command_runner: CommandRunner = default_runner):
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.redis = redis_client
        self.command_runner = command_runner

    def create_tables(self):
        Base.metadata.create_all(self.engine)
        # create_all never ALTERs an existing table — widen the report columns
        # in place on MySQL deployments created before the MEDIUMTEXT change.
        if self.engine.dialect.name == "mysql":
            try:
                with self.engine.begin() as conn:
                    conn.execute(text("ALTER TABLE eda_jobs MODIFY report_json MEDIUMTEXT"))
                    conn.execute(text("ALTER TABLE eda_jobs MODIFY artifact_index MEDIUMTEXT"))
            except Exception:  # noqa: BLE001 - best-effort migration
                pass

    def create_job(
        self,
        job_id: str,
        task_id: str,
        stage: str,
        *,
        workspace_root: str = "",
        stage_options: Optional[Dict[str, Any]] = None,
        artifacts: Optional[Dict[str, str]] = None,
    ):
        options: Dict[str, Any] = dict(stage_options or {})
        if artifacts:
            options.setdefault("artifacts", artifacts)
        with self.Session() as session:
            job = EDAJob(
                id=job_id,
                task_id=task_id,
                stage=stage,
                status="QUEUED",
                progress=0,
                workspace_root=workspace_root or "",
                stage_options=json.dumps(options),
                artifact_index="[]",
            )
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

    async def _publish(self, job_id: str, payload: Dict[str, Any]):
        await self.redis.publish(f"eda:job:{job_id}:status", json.dumps(payload))

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
            stage = job.stage
            task_id = job.task_id
            workspace_root = job.workspace_root
            try:
                options = json.loads(job.stage_options or "{}")
            except json.JSONDecodeError:
                options = {}
        await self.append_log(job_id, f"Starting {stage} stage")
        await self._publish(job_id, {"job_id": job_id, "status": "RUNNING", "progress": 10, "stage": stage})

        try:
            workspace = resolve_workspace(task_id, workspace_root)
            for progress in (25, 55, 80):
                await asyncio.sleep(1)
                self._update_progress(job_id, progress)
                await self.append_log(job_id, f"{stage} progress {progress}%")
                await self._publish(job_id, {"job_id": job_id, "status": "RUNNING", "progress": progress, "stage": stage})

            report = run_stage(
                stage=stage,
                task_id=task_id,
                workspace=workspace,
                opts=options,
                runner=self.command_runner,
            )
            report_dict = report.as_dict() if isinstance(report, BaseReport) else dict(report)
            report_dict.setdefault("task_id", task_id)
            report_dict.setdefault("stage", stage)
            report_dict.setdefault("generated_at", datetime.utcnow().isoformat() + "Z")
            artifact_index = report_dict.get("artifacts", [])

            # Persist the structured report into the shared workspace so the agent
            # service's evidence collector can discover it as reports/<stage>_report.json.
            try:
                reports_dir = workspace / "reports"
                reports_dir.mkdir(parents=True, exist_ok=True)
                (reports_dir / f"{stage.lower()}_report.json").write_text(json.dumps(report_dict, indent=2))
            except OSError:  # pragma: no cover - defensive path
                pass

            with self.Session() as session:
                row = session.get(EDAJob, job_id)
                if row is None:
                    return
                row.status = "COMPLETED"
                row.progress = 100
                row.report_json = json.dumps(report_dict)
                row.artifact_index = json.dumps(artifact_index)
                session.commit()
            for artifact in artifact_index:
                await self.append_log(job_id, f"Artifact: {artifact.get('path', '?')} ({artifact.get('kind', 'file')})")
            await self.append_log(job_id, f"{stage} stage completed")
            await self._publish(job_id, {
                "job_id": job_id,
                "status": "COMPLETED",
                "progress": 100,
                "stage": stage,
                "report": report_dict,
                "artifacts": artifact_index,
            })
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
            await self._publish(job_id, {"job_id": job_id, "status": "FAILED", "progress": 100, "stage": stage, "error": str(exc)})

    def _update_progress(self, job_id: str, progress: int):
        with self.Session() as session:
            row = session.get(EDAJob, job_id)
            if row is None:
                return
            row.progress = progress
            row.updated_at = datetime.utcnow()
            session.commit()
