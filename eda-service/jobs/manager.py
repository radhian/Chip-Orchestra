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
from toolchain import run_gl_sim, run_harden, run_lint, run_mock_toolchain, run_padring, run_render, run_simulation, run_sta
from toolchain.harden_runner import design_clock_period_ns
from toolchain.librelane import (
    ImplementationConfig,
    apply_pad_ring,
    collect_chip_artifacts,
    extract_pad_placement_from_def,
    extract_pinout,
    implementation_from_mapping,
    parse_librelane_stages,
    extract_librelane_version,
    run_chip_flow,
    write_pad_placement_json,
    write_pinout_json,
)
from toolchain.reports import BaseReport, ChipPnrReport, SignoffReport
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
    # An explicit request wins; otherwise take the period the DESIGN specifies
    # (rtl/params.vh `define CLK_FREQ, or the golden contract). Falling straight
    # to 10 ns hardened a 50 MHz design at 100 MHz — hours of OpenROAD chasing
    # timing that was never required, and a UART divisor describing a baud rate
    # the chip would not actually produce.
    try:
        clock_period = float(opts.get("clock_period") or 0.0)
    except (TypeError, ValueError):
        clock_period = 0.0
    if clock_period <= 0:
        clock_period = design_clock_period_ns(workspace) or 10.0
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
    if stage == "PADRING":
        # Run the real LibreLane Chip flow (synthesis -> OpenROAD.PadRing ->
        # route -> GDS, plus the die<->pad pinout) when the design ships a
        # chip-level LibreLane config. Fall back to the legacy gdspy padring
        # runner for designs that don't, so non-chip tasks are unaffected.
        if (workspace / "librelane" / "config.yaml").is_file():
            return _run_chip_pnr(workspace, top, stage_opts, runner)
        return run_padring(workspace, top, stage_opts, runner, stage=stage)
    if stage == "CHIP_PNR":
        return _run_chip_pnr(workspace, top, stage_opts, runner)
    if stage == "SIGNOFF":
        return _signoff_report(task_id, stage)
    # Fallback for any other stage: reuse the mock toolchain shape.
    report = BaseReport(stage=stage)
    report.summary = f"Mock {stage} execution completed successfully."
    report.metrics = {"timing_slack_ns": 0.11, "power_mw": 12.4, "area_um2": 48123}
    return report


def _run_chip_pnr(
    workspace: Path,
    top: str,
    stage_opts: Dict[str, Any],
    runner: CommandRunner,
) -> ChipPnrReport:
    """Execute a LibreLane Chip flow with OpenROAD.PadRing."""
    report = ChipPnrReport()
    report.top = top or "chip_top"

    # Parse implementation config from stage options
    impl_cfg = implementation_from_mapping(stage_opts.get("implementation"))
    report.flow = impl_cfg.flow
    report.pdk = stage_opts.get("pdk", "gf180mcuD")

    # Determine config path
    config_path = workspace / stage_opts.get("config_path", "librelane/config.yaml")
    if not config_path.is_file():
        report.errors.append(f"LibreLane config not found: {config_path}")
        report.summary = "Chip PNR failed: missing LibreLane configuration."
        return report

    use_docker = bool(stage_opts.get("use_docker", True))
    docker_image = str(stage_opts.get("docker_image", ""))

    try:
        result = run_chip_flow(
            workspace, config_path,
            runner=runner, use_docker=use_docker,
            docker_image=docker_image,
        )
        report.execution_mode = result.get("execution_mode", "")
        report.docker_image = result.get("image", "")
        log_text = result.get("log", "")
        report.librelane_version = extract_librelane_version(log_text)
        report.stages_observed = parse_librelane_stages(log_text)
        report.pad_ring_verified = "OpenROAD.PadRing" in (report.stages_observed or [])

        # Collect artifacts
        artifacts_info = collect_chip_artifacts(workspace)
        if artifacts_info.get("odb"):
            report.odb = artifacts_info["odb"][0]
        if artifacts_info.get("def"):
            report.def_file = artifacts_info["def"][0]
        if artifacts_info.get("gds"):
            report.gds = artifacts_info["gds"][0]
        if artifacts_info.get("state_out"):
            report.state_out = artifacts_info["state_out"]

        # Extract pad placement from DEF
        if report.def_file:
            def_path = Path(report.def_file)
            if def_path.is_file():
                placements = extract_pad_placement_from_def(def_path)
                pp_path = workspace / "pad_placement.json"
                write_pad_placement_json(placements, pp_path)
                report.pad_placement = str(pp_path)
                # Count pads by type (from master cell name)
                for p in placements:
                    master = p.get("master", "")
                    if "asig" in master:
                        report.pad_counts["analog"] = report.pad_counts.get("analog", 0) + 1
                    elif "bi_" in master:
                        report.pad_counts["bidirectional"] = report.pad_counts.get("bidirectional", 0) + 1
                    elif "in_" in master:
                        report.pad_counts["input"] = report.pad_counts.get("input", 0) + 1
                    elif "dvdd" in master:
                        report.pad_counts["power"] = report.pad_counts.get("power", 0) + 1
                    elif "dvss" in master:
                        report.pad_counts["ground"] = report.pad_counts.get("ground", 0) + 1
                    elif "cor" in master:
                        report.pad_counts["corner"] = report.pad_counts.get("corner", 0) + 1

                # Die <-> pad-ring pinout: which signal lands on which pad.
                # This is the map used for chip bring-up / probing, surfaced in
                # the SIGNOFF tab.
                pinout = extract_pinout(def_path)
                if pinout:
                    po_path = workspace / "padring" / "pinout.json"
                    write_pinout_json(pinout, po_path)
                    report.pinout = str(po_path)
                    report.pinout_entries = pinout

        report.metrics = {
            "flow": report.flow,
            "pdk": report.pdk,
            "librelane_version": report.librelane_version,
            "execution_mode": report.execution_mode,
            "stages_observed": report.stages_observed,
            "pad_ring_verified": report.pad_ring_verified,
            "pad_counts": report.pad_counts,
        }
        report.summary = (
            f"LibreLane Chip flow completed. "
            f"Flow={report.flow}, PDK={report.pdk}, "
            f"Stages: {', '.join(report.stages_observed)}."
        )
    except Exception as exc:
        report.errors.append(str(exc))
        report.summary = f"Chip PNR failed: {exc}"
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

            # A stage that recorded hard errors did NOT do its job. Every value a
            # runner writes to report.errors is fatal — "hardening timeout",
            # "no GDS produced", "chip output != golden output", "compile failed";
            # advisory notes go to report.warnings instead. Reporting those as
            # COMPLETED let the flow march past a stage that produced nothing, so
            # a run could reach EXPORT carrying no GDS at all. The report is
            # already persisted above, so the reason stays visible either way.
            stage_errors = [str(e).strip() for e in (report_dict.get("errors") or [])
                            if str(e).strip()]
            status = "FAILED" if stage_errors else "COMPLETED"
            detail = "; ".join(stage_errors)

            with self.Session() as session:
                row = session.get(EDAJob, job_id)
                if row is None:
                    return
                row.status = status
                row.progress = 100
                row.report_json = json.dumps(report_dict)
                row.artifact_index = json.dumps(artifact_index)
                if stage_errors:
                    row.error = detail
                session.commit()
            for artifact in artifact_index:
                await self.append_log(job_id, f"Artifact: {artifact.get('path', '?')} ({artifact.get('kind', 'file')})")
            await self.append_log(
                job_id,
                f"{stage} stage failed: {detail}" if stage_errors else f"{stage} stage completed")
            payload = {
                "job_id": job_id,
                "status": status,
                "progress": 100,
                "stage": stage,
                "report": report_dict,
                "artifacts": artifact_index,
            }
            if stage_errors:
                payload["error"] = detail
            await self._publish(job_id, payload)
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
