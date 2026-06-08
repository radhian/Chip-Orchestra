"""FastAPI application exposing the Chip Orchestra task API.

Every route mirrors a call in the frontend's `src/api/tasks.ts`, returning the
exact camelCase shapes from `src/types/chiporchestra.ts`.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import runner
from .config import get_settings
from .models import (
    ApprovalPayload,
    ArtifactItem,
    CreateTaskInput,
    DiagnosisItem,
    ExportBundleResponse,
    ProposePatchPayload,
    RunbookEvent,
    SignoffStatus,
    StatusResponse,
    TaskDetail,
    TaskStage,
    TaskSummary,
    WaiverPayload,
    WorkspaceFileContent,
    WorkspaceFileSummary,
)
from .store import TaskRecord, get_store, now_label

logging.basicConfig(level=logging.INFO)

settings = get_settings()
app = FastAPI(title="Chip Orchestra Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require(task_id: str) -> TaskRecord:
    record = get_store().get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return record


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": settings.llm_provider, "model": settings.ollama_model}


# --- tasks ------------------------------------------------------------------
@app.get("/api/tasks", response_model=list[TaskSummary])
def list_tasks(
    owner: str | None = Query(default=None),
    status: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    repo: str | None = Query(default=None),
    needs_review: bool | None = Query(default=None),
    failed: bool | None = Query(default=None),
) -> list[TaskSummary]:
    summaries = get_store().list_summaries()

    def keep(s: TaskSummary) -> bool:
        if owner == "me" and not s.mine:
            return False
        if owner and owner != "me" and s.ownerId != owner:
            return False
        if failed and s.tone != "failed":
            return False
        if needs_review and not (s.needsReview or s.tone == "review"):
            return False
        if stage and s.currentStage != stage:
            return False
        if status and s.statusLabel != status:
            return False
        if repo and repo.lower() not in s.repoName.lower():
            return False
        return True

    return [s for s in summaries if keep(s)]


@app.post("/api/tasks", response_model=TaskDetail)
def create_task(body: CreateTaskInput) -> TaskDetail:
    return runner.create_task(body)


@app.get("/api/tasks/{task_id}", response_model=TaskDetail)
def get_task(task_id: str) -> TaskDetail:
    return _require(task_id).detail


@app.get("/api/tasks/{task_id}/stages", response_model=list[TaskStage])
def get_stages(task_id: str) -> list[TaskStage]:
    return _require(task_id).detail.stages


@app.post("/api/tasks/{task_id}/retry", response_model=StatusResponse)
def retry_task(task_id: str) -> StatusResponse:
    if not runner.retry_task(task_id):
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return StatusResponse(status="queued")


@app.post("/api/tasks/{task_id}/stop", response_model=StatusResponse)
def stop_task(task_id: str) -> StatusResponse:
    _require(task_id)
    return StatusResponse(status="stopping" if runner.stop_task(task_id) else "noop")


@app.post("/api/tasks/{task_id}/resume", response_model=StatusResponse)
def resume_task(task_id: str) -> StatusResponse:
    _require(task_id)
    return StatusResponse(status="resumed" if runner.resume_task_run(task_id) else "noop")


@app.post("/api/tasks/{task_id}/cancel", response_model=StatusResponse)
def cancel_task(task_id: str) -> StatusResponse:
    _require(task_id)
    return StatusResponse(status="cancelling" if runner.cancel_task(task_id) else "noop")


# --- attempt-scoped reads ---------------------------------------------------
@app.get("/api/tasks/{task_id}/attempts/latest/events", response_model=list[RunbookEvent])
def get_events(task_id: str) -> list[RunbookEvent]:
    return _require(task_id).events


@app.get("/api/tasks/{task_id}/attempts/latest/artifacts", response_model=list[ArtifactItem])
def get_artifacts(task_id: str) -> list[ArtifactItem]:
    return _require(task_id).artifacts


@app.get("/api/tasks/{task_id}/attempts/latest/diagnosis", response_model=list[DiagnosisItem])
def get_diagnosis(task_id: str) -> list[DiagnosisItem]:
    return _require(task_id).diagnoses


# --- workspace --------------------------------------------------------------
@app.get("/api/tasks/{task_id}/workspace/files", response_model=list[WorkspaceFileSummary])
def get_workspace_files(task_id: str) -> list[WorkspaceFileSummary]:
    return _require(task_id).workspace_files


@app.get("/api/tasks/{task_id}/workspace/file", response_model=WorkspaceFileContent)
def get_workspace_file(task_id: str, path: str = Query(...)) -> WorkspaceFileContent:
    _require(task_id)
    try:
        content = get_store().read_workspace_file(task_id, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorkspaceFileContent(path=path, content=content)


@app.post("/api/tasks/{task_id}/workspace/propose-patch", response_model=StatusResponse)
def propose_patch(task_id: str, body: ProposePatchPayload) -> StatusResponse:
    _require(task_id)
    runner.propose_patch(task_id, body.instruction)
    return StatusResponse(status="queued")


# --- signoff / approvals / waivers / export ---------------------------------
@app.get("/api/tasks/{task_id}/signoff/status", response_model=SignoffStatus)
def get_signoff(task_id: str) -> SignoffStatus:
    return _require(task_id).signoff


@app.post("/api/tasks/{task_id}/approvals/{stage}", response_model=StatusResponse)
def submit_approval(task_id: str, stage: str, body: ApprovalPayload) -> StatusResponse:
    _require(task_id)
    store = get_store()

    def _apply(rec: TaskRecord) -> None:
        approve = body.decision == "approve"
        rec.signoff.stateLabel = "Approved" if approve else "Needs follow-up"
        rec.signoff.message = (
            "Approval recorded. The task can move into export packaging."
            if approve
            else "Approval rejected. Review the diagnosis and rerun the required stages."
        )
        if approve and rec.signoff.checklist:
            rec.signoff.checklist[-1].done = True
        rec.needs_review = not approve
        for st in rec.detail.stages:
            st.pendingApproval = False

    store.mutate(task_id, _apply)
    store.add_event(
        task_id,
        f"Approval {body.decision}d for {stage}",
        body.comment or f"Stage `{stage}` review {body.decision}d by the engineer.",
        "success" if body.decision == "approve" else "warning",
    )
    return StatusResponse(status="recorded")


@app.post("/api/tasks/{task_id}/waivers", response_model=StatusResponse)
def create_waiver(task_id: str, body: WaiverPayload) -> StatusResponse:
    _require(task_id)
    get_store().add_event(task_id, f"Waiver requested: {body.title}", body.detail, "warning")
    return StatusResponse(status="queued")


@app.post("/api/tasks/{task_id}/export-bundle", response_model=ExportBundleResponse)
def export_bundle(task_id: str) -> ExportBundleResponse:
    _require(task_id)
    artifact_id = f"bundle-{uuid.uuid4().hex[:8]}"
    store = get_store()
    bundle_path = runner.export_bundle(task_id, artifact_id)
    store.add_artifact(task_id, f"{artifact_id}.zip", "Delivery", "Signoff agent")
    store.add_event(
        task_id,
        "Export bundle assembled",
        f"Handoff bundle written to {bundle_path}.",
        "success",
    )
    return ExportBundleResponse(artifactId=artifact_id, status="ready")
