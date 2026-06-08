"""Task lifecycle: build the initial record, then drive the agent pipeline in
the background, mapping its progress onto the Chip Orchestra task model."""

from __future__ import annotations

import logging
import shutil
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .agent.graph import (
    STAGE_DELIVER,
    STAGE_IMPL,
    STAGE_PLAN,
    STAGE_SPEC,
    STAGE_VERIFY,
    Reporter,
    build_pipeline,
)
from . import control
from .agent.llm import complete, extract_code_block, guess_top_module
from .config import get_settings
from .control import PipelineCancelled, PipelineStopped
from .models import CreateTaskInput, DiagnosisItem, TaskAttempt, TaskDetail, TaskStage
from .store import TaskRecord, TaskStore, get_store, now_label

logger = logging.getLogger("chip_orchestra.runner")

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent")
# Compiled pipelines kept alive per task so a paused run can resume from its
# in-memory checkpoint. Cleared on completion/cancel.
_pipelines: dict[str, object] = {}

DEFAULT_OWNER_NAME = "Engineer"
DEFAULT_OWNER_ID = "engineer"

_STAGES = [
    (STAGE_SPEC, "Spec intake"),
    (STAGE_PLAN, "Agent planning"),
    (STAGE_VERIFY, "Verification loop"),
    (STAGE_IMPL, "Implementation"),
    (STAGE_DELIVER, "Delivery"),
]

_PDK_MAP = {"sky130": "sky130A", "gf180": "gf180mcuD", "gf180mcu": "gf180mcuD"}


def _pdk_label(pdk_id: str, stdcell: str) -> str:
    if pdk_id.startswith("sky130"):
        return "Sky130 HD"
    if pdk_id.startswith("gf180"):
        return "GF180MCU"
    return f"{pdk_id} / {stdcell}"


def _review_gate_label(gates: list[str]) -> str:
    has_synth = "BEFORE_SYNTH" in gates
    has_signoff = "BEFORE_SIGNOFF" in gates
    if has_synth and has_signoff:
        return "Require engineer approval before synthesis and before signoff packaging"
    if has_synth:
        return "Require engineer approval before synthesis"
    if has_signoff:
        return "Require engineer approval before signoff packaging"
    return "Autonomous run (no manual gates)"


def _repo_name(payload) -> str:
    if payload.repo_mode == "TEMPLATE":
        return payload.template_id or "digital-block-starter"
    return payload.repo_id or "chiporchestra/workspace"


def _runs_harden(launch_mode: str) -> bool:
    settings = get_settings()
    return settings.run_harden and launch_mode in ("FULL_FLOW_GATED", "SYNTH_ONLY")


def create_task(payload_input: CreateTaskInput) -> TaskDetail:
    store = get_store()
    settings = get_settings()
    task = payload_input.task
    task_id = store.new_id(task.name)
    model = task.model or settings.ollama_model

    stages = [
        TaskStage(key=key, label=label, status="active" if i == 0 else "queued")
        for i, (key, label) in enumerate(_STAGES)
    ]
    detail = TaskDetail(
        id=task_id,
        name=task.name,
        description=task.design_brief,
        ownerName=task.owner_name or DEFAULT_OWNER_NAME,
        ownerId=task.owner_id or DEFAULT_OWNER_ID,
        currentStage="Spec intake",
        etaLabel="Queued",
        statusLabel="Running",
        tone="running",
        repoName=_repo_name(task),
        pdkLabel=_pdk_label(task.pdk_id, task.stdcell_lib_id),
        reviewGateLabel=_review_gate_label(task.review_gates),
        runtimeLabel=f"Ollama {model} + iverilog/LibreLane",
        artifactLineageCount=0,
        stages=stages,
        attempts=[TaskAttempt(id="attempt-1", status="queued", startedAt=now_label(), updatedAt=now_label())],
    )

    run_harden = _runs_harden(task.launch_mode)
    meta = {
        "brief": task.design_brief,
        "model": model,
        "clock_period_ns": task.clock_period_ns or 10.0,
        "pdk": _PDK_MAP.get(task.pdk_id, settings.default_pdk),
        "stdcell": task.stdcell_lib_id,
        "run_harden": run_harden,
        "max_retries": task.agent_policy.retry_budget or settings.max_retries,
        "research_depth": task.research_depth,
    }
    record = TaskRecord(
        detail,
        needs_review="BEFORE_SIGNOFF" in task.review_gates,
        mine=(task.owner_id or DEFAULT_OWNER_ID) == DEFAULT_OWNER_ID,
        summary_description="Agentic RTL-to-GDSII task with live artifact lineage.",
        meta=meta,
    )
    store.add(record)
    store.add_event(task_id, "Task created", "Enqueued with the selected repo, PDK, and review gates.", "info")

    _launch(task_id, meta)
    return detail


def retry_task(task_id: str) -> bool:
    store = get_store()
    record = store.get(task_id)
    if record is None:
        return False
    store.new_attempt(task_id)
    # Reset stage timeline for a fresh attempt.
    for i, (key, _label) in enumerate(_STAGES):
        store.set_stage(task_id, key, "active" if i == 0 else "queued",
                        pendingApproval=False, waiverReviewPending=False)
    store.set_status(task_id, status_label="Running", tone="running", current_stage="Spec intake",
                     eta_label="Queued", attempt_status="running")
    store.add_event(task_id, "Retry requested", "Re-running the agentic pipeline from spec intake.", "info")
    _launch(task_id, record.meta)
    return True


def _launch(task_id: str, meta: dict) -> None:
    store = get_store()
    state = {
        "task_id": task_id,
        "brief": meta["brief"],
        "model": meta.get("model"),
        "clock_period_ns": meta.get("clock_period_ns", 10.0),
        "pdk": meta.get("pdk"),
        "stdcell": meta.get("stdcell"),
        "run_harden": meta.get("run_harden", True),
        "max_retries": meta.get("max_retries", get_settings().max_retries),
        "research_depth": meta.get("research_depth", "MEDIUM"),
        "error_count": 0,
    }
    # Build the pipeline once (with its checkpointer) and keep it for resume.
    _pipelines[task_id] = build_pipeline(Reporter(store, task_id))
    control.set_status(task_id, control.RUNNING)
    _executor.submit(_run_pipeline, store, task_id, state)


# --- run control: stop (pause) / resume / cancel ---------------------------
def stop_task(task_id: str) -> bool:
    """Request a pause at the next step boundary."""
    if control.get_status(task_id) != control.RUNNING:
        return False
    control.set_status(task_id, control.STOPPING)
    store = get_store()
    store.set_status(task_id, status_label="Stopping", tone="review", eta_label="Stopping")
    store.add_event(task_id, "Stop requested", "Pausing as soon as the current step yields…", "info")
    return True


def resume_task_run(task_id: str) -> bool:
    """Resume a paused run from its checkpoint; restart from scratch if the
    checkpoint is gone (e.g. after a server restart)."""
    store = get_store()
    if control.get_status(task_id) == control.PAUSED and task_id in _pipelines:
        control.set_status(task_id, control.RUNNING)
        store.set_status(task_id, status_label="Running", tone="running", attempt_status="running")
        store.add_event(task_id, "Run resumed", "Continuing from the last checkpoint.", "info")
        _executor.submit(_run_pipeline, store, task_id, None)
        return True
    # No live checkpoint — fall back to a fresh run if the task still exists.
    if store.get(task_id) is not None:
        return retry_task(task_id)
    return False


_TERMINAL_STATES = {"Cancelled", "Passed"}


def cancel_task(task_id: str) -> bool:
    """Cancel a run. Works whether it's actively running, paused, or orphaned
    (e.g. shown 'Running' after a restart with no live thread behind it)."""
    store = get_store()
    record = store.get(task_id)
    if record is None or record.detail.statusLabel in _TERMINAL_STATES:
        return False

    status = control.get_status(task_id)
    if status in (control.RUNNING, control.STOPPING):
        # A live run is executing — flag it; the worker thread marks it cancelled.
        control.set_status(task_id, control.CANCELLING)
        store.set_status(task_id, status_label="Cancelling", tone="review", eta_label="Cancelling")
        store.add_event(task_id, "Cancel requested", "Cancelling as soon as the current step yields…", "warning")
        return True

    # No live run (paused, interrupted, failed, or orphaned) — cancel directly.
    control.set_status(task_id, control.CANCELLED)
    _pipelines.pop(task_id, None)
    store.set_status(task_id, status_label="Cancelled", tone="failed", current_stage="Cancelled",
                     eta_label="—", attempt_status="cancelled")
    store.add_event(task_id, "Run cancelled", "The run was cancelled.", "warning")
    return True


_PATCH_PROMPT = """\
Apply the following engineer instruction to this Verilog module and return the
complete, updated, synthesizable RTL.

Instruction:
\"\"\"{instruction}\"\"\"

Current RTL:
```verilog
{rtl}
```

Output ONLY the full updated RTL in a single ```verilog code block.
"""


def propose_patch(task_id: str, instruction: str) -> None:
    """Apply an engineer instruction to the latest top RTL via the agent."""
    store = get_store()
    store.add_event(task_id, "Patch requested", instruction, "info")
    _executor.submit(_run_patch, store, task_id, instruction)


def _run_patch(store: TaskStore, task_id: str, instruction: str) -> None:
    record = store.get(task_id)
    if record is None:
        return
    rtl_summary = next((f for f in record.workspace_files if f.path.startswith("rtl/")), None)
    if rtl_summary is None:
        store.add_event(task_id, "Patch skipped", "No RTL file is available to patch yet.", "warning")
        return
    try:
        current = store.read_workspace_file(task_id, rtl_summary.path)
        raw = complete(_PATCH_PROMPT.format(instruction=instruction, rtl=current),
                       model=record.meta.get("model"))
        updated = extract_code_block(raw, "verilog")
        top = guess_top_module(updated, fallback=rtl_summary.name.removesuffix(".v"))
        store.register_workspace_file(task_id, rtl_summary.path, updated,
                                      note="RTL revision (engineer patch)", status="RTL patch")
        store.add_artifact(task_id, rtl_summary.name, "RTL", "Workspace agent")
        store.add_event(task_id, "Patch applied", f"Updated `{top}` per the engineer instruction.", "success")
        store.set_diagnoses(task_id, [
            DiagnosisItem(
                id="diag-patch",
                title="Review the engineer patch before the next run",
                detail=f"Applied instruction: {instruction}",
                confidence="Engineer-directed change",
                primaryFile=rtl_summary.path,
                suggestedBy="Workspace agent",
            )
        ])
    except Exception as exc:  # noqa: BLE001
        logger.exception("Patch failed for task %s", task_id)
        store.add_event(task_id, "Patch failed", f"{type(exc).__name__}: {exc}", "warning")


def export_bundle(task_id: str, artifact_id: str) -> str:
    """Zip the task workspace into a downloadable handoff bundle; return its path."""
    store = get_store()
    ws = store.workspace_dir(task_id)
    bundles = ws / "bundles"
    bundles.mkdir(parents=True, exist_ok=True)
    archive_base = bundles / artifact_id
    # Archive rtl/, tb/, sim/, harden/, docs/ without recursing into prior bundles.
    staging = ws / ".bundle_staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    for sub in ("rtl", "tb", "sim", "harden", "docs"):
        src = ws / sub
        if src.exists():
            shutil.copytree(src, staging / sub)
    shutil.make_archive(str(archive_base), "zip", root_dir=str(staging))
    shutil.rmtree(staging, ignore_errors=True)
    zip_path = Path(str(archive_base) + ".zip")
    # Mirror the handoff bundle to object storage.
    from .persistence import get_persistence

    get_persistence().put_object(f"{task_id}/bundles/{artifact_id}.zip", zip_path)
    return str(zip_path)


def _run_pipeline(store: TaskStore, task_id: str, state: dict | None) -> None:
    """Run (or resume) the pipeline. ``state=None`` resumes from the checkpoint."""
    app = _pipelines.get(task_id)
    if app is None:
        return
    config = {"configurable": {"thread_id": task_id}, "recursion_limit": 60}
    try:
        app.invoke(state, config=config)
    except PipelineStopped:
        control.set_status(task_id, control.PAUSED)
        store.set_status(task_id, status_label="Paused", tone="review", current_stage="Paused",
                         eta_label="Paused", attempt_status="paused")
        store.add_event(task_id, "Run paused", "Stopped at a step boundary — resume to continue from here.", "warning")
    except PipelineCancelled:
        control.set_status(task_id, control.CANCELLED)
        _pipelines.pop(task_id, None)
        store.set_status(task_id, status_label="Cancelled", tone="failed", current_stage="Cancelled",
                         eta_label="—", attempt_status="cancelled")
        store.add_event(task_id, "Run cancelled", "The run was cancelled by the user.", "warning")
    except Exception as exc:  # noqa: BLE001 - surface failures into the runbook
        logger.exception("Pipeline crashed for task %s", task_id)
        control.clear(task_id)
        _pipelines.pop(task_id, None)
        store.add_event(task_id, "Pipeline error", f"{type(exc).__name__}: {exc}", "warning")
        store.set_status(task_id, status_label="Failed", tone="failed", current_stage="Error",
                         eta_label="Retry", attempt_status="failed")
        detail = "".join(traceback.format_exception(exc))[-1500:]
        store.register_workspace_file(task_id, "logs/error.log", detail, note="Pipeline error trace", status="Log")
    else:
        control.clear(task_id)
        _pipelines.pop(task_id, None)
