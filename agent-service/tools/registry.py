from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict

from redis import Redis

from context import files as wsfiles


class ToolRegistry:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.tools: Dict[str, Callable[..., Any]] = {
            "update_task_status": self.update_task_status,
            "track_task_progress": self.track_task_progress,
            "get_user_context": self.get_user_context,
            # NOTE: submit_eda_job / get_eda_result remain callable for backwards
            # compatibility, but EDA job submission is owned by the orchestrator
            # (Go) which fans out to the internal eda-service. These are thin
            # placeholders the agent should not rely on for real execution.
            "submit_eda_job": self.submit_eda_job,
            "get_eda_result": self.get_eda_result,
            # Legacy Redis-backed artifact helpers (kept for compatibility).
            "read_artifact": self.read_artifact,
            "write_artifact": self.write_artifact,
            # Real workspace-backed file/report tools.
            "list_workspace_files": self.list_workspace_files,
            "read_workspace_file": self.read_workspace_file,
            "write_workspace_file": self.write_workspace_file,
            "read_stage_report": self.read_stage_report,
            "write_stage_summary": self.write_stage_summary,
            "record_task_note": self.record_task_note,
            "record_artifact_metadata": self.record_artifact_metadata,
        }

    # ------------------------------------------------------------------
    # Existing Redis-backed status/progress tools (unchanged behavior)
    # ------------------------------------------------------------------
    def update_task_status(self, task_id: str, stage: str, payload: Dict[str, Any]):
        self.redis.set(f"agent:task_status:{task_id}:{stage}", json.dumps(payload))
        return {"status": "updated"}

    def track_task_progress(self, task_id: str, stage: str, payload: Dict[str, Any]):
        self.redis.rpush(f"agent:progress:{task_id}", json.dumps({"stage": stage, **payload}))
        return {"status": "tracked"}

    def get_user_context(self, task_id: str, stage: str, payload: Dict[str, Any]):
        return {
            "task_id": task_id,
            "stage": stage,
            "default_user": os.getenv("DEFAULT_FULL_NAME", "Admin Admin"),
            "username": os.getenv("DEFAULT_USERNAME", "admin"),
        }

    def submit_eda_job(self, task_id: str, stage: str, payload: Dict[str, Any]):
        # Owned by the orchestrator; kept as a placeholder to avoid breaking
        # callers that still reference the tool name.
        return {"job_id": f"mock-{task_id}-{stage.lower()}", "status": "queued", "owner": "orchestrator"}

    def get_eda_result(self, task_id: str, stage: str, payload: Dict[str, Any]):
        return {"task_id": task_id, "stage": stage, "status": "completed", "summary": "Mock EDA result", "owner": "orchestrator"}

    def read_artifact(self, task_id: str, stage: str, payload: Dict[str, Any]):
        path = payload.get("path", "")
        return self.redis.get(f"artifact:{task_id}:{path}") or ""

    def write_artifact(self, task_id: str, stage: str, payload: Dict[str, Any]):
        path = payload.get("path", f"reports/{stage.lower()}.md")
        content = payload.get("content", payload.get("summary", ""))
        self.redis.set(f"artifact:{task_id}:{path}", content)
        self.redis.hset(f"artifact:index:{task_id}", path, stage)
        return {"status": "written", "path": path}

    # ------------------------------------------------------------------
    # Real workspace-backed file/report tools
    # ------------------------------------------------------------------
    def _workspace(self, task_id: str, payload: Dict[str, Any]):
        return wsfiles.resolve_workspace(task_id, payload.get("workspace_root"))

    def list_workspace_files(self, task_id: str, stage: str, payload: Dict[str, Any]):
        workspace = self._workspace(task_id, payload)
        return {"files": wsfiles.list_files(workspace)}

    def read_workspace_file(self, task_id: str, stage: str, payload: Dict[str, Any]):
        workspace = self._workspace(task_id, payload)
        path = payload.get("path", "")
        try:
            return {"path": path, "content": wsfiles.read_file(workspace, path)}
        except (FileNotFoundError, wsfiles.UnsafePathError) as exc:
            return {"path": path, "error": str(exc)}

    def write_workspace_file(self, task_id: str, stage: str, payload: Dict[str, Any]):
        workspace = self._workspace(task_id, payload)
        path = payload.get("path", f"reports/{stage.lower()}.md")
        content = payload.get("content", payload.get("summary", ""))
        try:
            target = wsfiles.write_file(workspace, path, content)
        except wsfiles.UnsafePathError as exc:
            return {"status": "rejected", "path": path, "error": str(exc)}
        self.redis.hset(f"artifact:index:{task_id}", path, stage)
        return {"status": "written", "path": str(target.relative_to(workspace))}

    def read_stage_report(self, task_id: str, stage: str, payload: Dict[str, Any]):
        workspace = self._workspace(task_id, payload)
        report_stage = str(payload.get("report_stage", stage)).lower()
        path = payload.get("path", f"reports/{report_stage}_report.json")
        try:
            raw = wsfiles.read_file(workspace, path)
        except (FileNotFoundError, wsfiles.UnsafePathError) as exc:
            return {"path": path, "error": str(exc)}
        try:
            return {"path": path, "report": json.loads(raw)}
        except json.JSONDecodeError:
            return {"path": path, "content": raw}

    def write_stage_summary(self, task_id: str, stage: str, payload: Dict[str, Any]):
        workspace = self._workspace(task_id, payload)
        path = payload.get("path", f"reports/{stage.lower()}_summary.md")
        content = payload.get("content", payload.get("summary", ""))
        try:
            wsfiles.write_file(workspace, path, content)
        except wsfiles.UnsafePathError as exc:
            return {"status": "rejected", "path": path, "error": str(exc)}
        self.redis.hset(f"artifact:index:{task_id}", path, stage)
        return {"status": "written", "path": path}

    def record_task_note(self, task_id: str, stage: str, payload: Dict[str, Any]):
        note = payload.get("note", payload.get("summary", ""))
        self.redis.rpush(f"agent:notes:{task_id}", json.dumps({"stage": stage, "note": note}))
        return {"status": "recorded"}

    def record_artifact_metadata(self, task_id: str, stage: str, payload: Dict[str, Any]):
        path = payload.get("path", "")
        metadata = payload.get("metadata", {})
        self.redis.hset(f"artifact:metadata:{task_id}", path, json.dumps({"stage": stage, **metadata}))
        self.redis.hset(f"artifact:index:{task_id}", path, stage)
        return {"status": "recorded", "path": path}
