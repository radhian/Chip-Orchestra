"""In-memory task store with on-disk persistence.

One ``TaskRecord`` per design task holds everything the frontend reads: the
detail object, runbook events, artifacts, diagnoses, workspace file summaries
and the signoff status. Generated RTL/TB/SDC/GDS live as real files inside the
task's workspace directory; their content is read back on demand.

The store is the single source of truth shared between the API routes and the
background agent runner, so every mutation takes a re-entrant lock and persists
a small ``task.json`` snapshot for restart durability.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

from .config import get_settings
from .persistence import get_persistence
from .models import (
    ArtifactItem,
    DiagnosisItem,
    RunbookEvent,
    SignoffStatus,
    TaskAttempt,
    TaskDetail,
    TaskStage,
    TaskSummary,
    WorkspaceFileSummary,
)


def now_label() -> str:
    return datetime.now().strftime("%H:%M")


def _new_id(name: str) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
    slug = "-".join(filter(None, slug.split("-")))[:40] or "task"
    return f"{slug}-{uuid.uuid4().hex[:6]}"


class TaskRecord:
    """Mutable aggregate for a single task. Not thread-safe on its own; the
    owning :class:`TaskStore` serialises all access."""

    def __init__(
        self,
        detail: TaskDetail,
        *,
        needs_review: bool = False,
        mine: bool = True,
        summary_description: str | None = None,
        meta: dict | None = None,
    ) -> None:
        self.detail = detail
        self.needs_review = needs_review
        self.mine = mine
        self.summary_description = summary_description or detail.description
        self.meta = meta or {}
        self.events: list[RunbookEvent] = []
        self.artifacts: list[ArtifactItem] = []
        self.diagnoses: list[DiagnosisItem] = []
        self.workspace_files: list[WorkspaceFileSummary] = []
        self.signoff: SignoffStatus = SignoffStatus(
            stateLabel="Not started",
            message="Signoff becomes available once verification and implementation finish.",
            packageContents=["Signoff bundle is generated after implementation"],
            checklist=[],
        )

    def to_summary(self) -> TaskSummary:
        d = self.detail
        return TaskSummary(
            id=d.id,
            name=d.name,
            description=self.summary_description,
            ownerName=d.ownerName,
            ownerId=d.ownerId,
            currentStage=d.currentStage,
            etaLabel=d.etaLabel,
            statusLabel=d.statusLabel,
            tone=d.tone,
            repoName=d.repoName,
            needsReview=self.needs_review or None,
            mine=self.mine or None,
        )

    def to_json(self) -> dict:
        return {
            "detail": self.detail.model_dump(),
            "needs_review": self.needs_review,
            "mine": self.mine,
            "summary_description": self.summary_description,
            "meta": self.meta,
            "events": [e.model_dump() for e in self.events],
            "artifacts": [a.model_dump() for a in self.artifacts],
            "diagnoses": [x.model_dump() for x in self.diagnoses],
            "workspace_files": [f.model_dump() for f in self.workspace_files],
            "signoff": self.signoff.model_dump(),
        }

    @classmethod
    def from_json(cls, data: dict) -> "TaskRecord":
        rec = cls(
            TaskDetail(**data["detail"]),
            needs_review=data.get("needs_review", False),
            mine=data.get("mine", True),
            summary_description=data.get("summary_description"),
            meta=data.get("meta", {}),
        )
        rec.events = [RunbookEvent(**e) for e in data.get("events", [])]
        rec.artifacts = [ArtifactItem(**a) for a in data.get("artifacts", [])]
        rec.diagnoses = [DiagnosisItem(**x) for x in data.get("diagnoses", [])]
        rec.workspace_files = [WorkspaceFileSummary(**f) for f in data.get("workspace_files", [])]
        if data.get("signoff"):
            rec.signoff = SignoffStatus(**data["signoff"])
        return rec


class TaskStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, TaskRecord] = {}
        self._root = get_settings().workspace_path
        self._persistence = get_persistence()
        self._hydrate()

    # --- lifecycle ---------------------------------------------------------
    def new_id(self, name: str) -> str:
        return _new_id(name)

    def workspace_dir(self, task_id: str) -> Path:
        path = self._root / task_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def add(self, record: TaskRecord) -> TaskRecord:
        with self._lock:
            self._records[record.detail.id] = record
            self._persist(record)
        return record

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._records.get(task_id)

    def list_summaries(self) -> list[TaskSummary]:
        with self._lock:
            return [r.to_summary() for r in self._records.values()]

    # --- mutations (each persists) ----------------------------------------
    def mutate(self, task_id: str, fn) -> None:
        """Apply ``fn(record)`` under the lock and persist."""
        with self._lock:
            rec = self._records.get(task_id)
            if rec is None:
                return
            fn(rec)
            self._persist(rec)

    def add_event(
        self, task_id: str, title: str, detail: str, tone: str = "info"
    ) -> None:
        event = RunbookEvent(
            id=f"event-{uuid.uuid4().hex[:8]}",
            time=now_label(),
            title=title,
            detail=detail,
            tone=tone,  # type: ignore[arg-type]
        )
        self.mutate(task_id, lambda rec: rec.events.insert(0, event))
        # Also append to the durable event log (Postgres) for queryable history.
        self._persistence.append_event(task_id, event.model_dump())

    def set_stage(self, task_id: str, key: str, status: str, **flags) -> None:
        def _apply(rec: TaskRecord) -> None:
            for st in rec.detail.stages:
                if st.key == key:
                    st.status = status  # type: ignore[assignment]
                    for k, v in flags.items():
                        setattr(st, k, v)

        self.mutate(task_id, _apply)

    def set_status(
        self,
        task_id: str,
        *,
        status_label: str | None = None,
        tone: str | None = None,
        current_stage: str | None = None,
        eta_label: str | None = None,
        attempt_status: str | None = None,
    ) -> None:
        def _apply(rec: TaskRecord) -> None:
            d = rec.detail
            if status_label is not None:
                d.statusLabel = status_label
            if tone is not None:
                d.tone = tone  # type: ignore[assignment]
            if current_stage is not None:
                d.currentStage = current_stage
            if eta_label is not None:
                d.etaLabel = eta_label
            if attempt_status is not None and d.attempts:
                d.attempts[0].status = attempt_status
                d.attempts[0].updatedAt = now_label()

        self.mutate(task_id, _apply)

    def add_artifact(self, task_id: str, name: str, type_: str, owner: str) -> None:
        def _apply(rec: TaskRecord) -> None:
            rec.artifacts.append(
                ArtifactItem(id=f"artifact-{uuid.uuid4().hex[:8]}", name=name, type=type_, owner=owner)
            )
            rec.detail.artifactLineageCount = len(rec.artifacts)

        self.mutate(task_id, _apply)

    def set_diagnoses(self, task_id: str, diagnoses: list[DiagnosisItem]) -> None:
        self.mutate(task_id, lambda rec: setattr(rec, "diagnoses", diagnoses))

    def register_workspace_file(
        self, task_id: str, rel_path: str, content: str, *, note: str, status: str
    ) -> None:
        """Write ``content`` to the task workspace and register a summary."""
        ws = self.workspace_dir(task_id)
        file_path = ws / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        summary = WorkspaceFileSummary(path=rel_path, name=Path(rel_path).name, note=note, status=status)

        def _apply(rec: TaskRecord) -> None:
            rec.workspace_files = [f for f in rec.workspace_files if f.path != rel_path]
            rec.workspace_files.append(summary)

        self.mutate(task_id, _apply)
        # Mirror the file to object storage (S3/MinIO) + record metadata in Postgres.
        self._persistence.put_file(task_id, summary.model_dump(), file_path)

    def set_signoff(self, task_id: str, signoff: SignoffStatus) -> None:
        self.mutate(task_id, lambda rec: setattr(rec, "signoff", signoff))

    def clear_workspace_subdir(self, task_id: str, subdir: str) -> None:
        """Delete files under a workspace subdir and drop their summaries.

        Used before rewriting RTL so a re-generated design doesn't collide with
        stale per-module files (which would be duplicate module definitions)."""
        ws = self.workspace_dir(task_id)
        target = ws / subdir
        if target.exists():
            for path in target.glob("*"):
                if path.is_file():
                    path.unlink()

        prefix = f"{subdir}/"

        def _apply(rec: TaskRecord) -> None:
            rec.workspace_files = [f for f in rec.workspace_files if not f.path.startswith(prefix)]

        self.mutate(task_id, _apply)

    def read_workspace_file(self, task_id: str, rel_path: str) -> str:
        ws = self.workspace_dir(task_id)
        target = (ws / rel_path).resolve()
        # Guard against path traversal outside the task workspace.
        if not str(target).startswith(str(ws.resolve())):
            raise ValueError("Invalid workspace path")
        if not target.exists():
            # Local cache miss (e.g. after a fresh checkout) — pull from object storage.
            blob = self._persistence.get_file(task_id, rel_path)
            if blob is not None:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(blob)
                return blob.decode("utf-8", errors="replace")
            return f"// File not found in workspace: {rel_path}"
        return target.read_text(encoding="utf-8", errors="replace")

    def new_attempt(self, task_id: str) -> None:
        def _apply(rec: TaskRecord) -> None:
            n = len(rec.detail.attempts) + 1
            rec.detail.attempts.insert(
                0,
                TaskAttempt(
                    id=f"attempt-{n}",
                    status="queued",
                    startedAt=now_label(),
                    updatedAt=now_label(),
                ),
            )

        self.mutate(task_id, _apply)

    # --- persistence -------------------------------------------------------
    def _persist(self, rec: TaskRecord) -> None:
        # Local working snapshot (fast reads) + durable mirror to Postgres.
        ws = self.workspace_dir(rec.detail.id)
        (ws / "task.json").write_text(json.dumps(rec.to_json(), indent=2), encoding="utf-8")
        self._persistence.save_task(rec.to_json())

    def _hydrate(self) -> None:
        """Load existing tasks from Postgres (if enabled) else from local disk."""
        if self._persistence.db_enabled:
            for data in self._persistence.load_tasks():
                try:
                    rec = TaskRecord.from_json(data)
                    self._records[rec.detail.id] = rec
                except Exception:  # pragma: no cover
                    continue
        if not self._records:
            self._load_from_disk()
        self._reconcile_orphaned()

    # Tasks shown as active but with no live run (the process restarted mid-run).
    _ORPHANED_STATES = {"Running", "Stopping", "Cancelling", "Queued"}

    def _reconcile_orphaned(self) -> None:
        """A run can't survive a process restart (in-memory pipeline/checkpoint are
        gone), so any task left "Running" is marked Interrupted and made retryable."""
        for rec in self._records.values():
            if rec.detail.statusLabel not in self._ORPHANED_STATES:
                continue
            rec.detail.statusLabel = "Interrupted"
            rec.detail.tone = "failed"
            rec.detail.etaLabel = "Retry"
            for st in rec.detail.stages:
                if st.status == "active":
                    st.status = "failed"
            if rec.detail.attempts:
                rec.detail.attempts[0].status = "interrupted"
            rec.events.insert(
                0,
                RunbookEvent(
                    id=f"event-{uuid.uuid4().hex[:8]}",
                    time=now_label(),
                    title="Run interrupted",
                    detail="The backend restarted while this run was active. Retry to run it again.",
                    tone="warning",
                ),
            )
            self._persist(rec)

    def _load_from_disk(self) -> None:
        for task_json in self._root.glob("*/task.json"):
            try:
                data = json.loads(task_json.read_text(encoding="utf-8"))
                rec = TaskRecord.from_json(data)
                self._records[rec.detail.id] = rec
            except Exception:  # pragma: no cover - tolerate corrupt snapshots
                continue


_store: TaskStore | None = None


def get_store() -> TaskStore:
    global _store
    if _store is None:
        _store = TaskStore()
    return _store
