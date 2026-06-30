from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict

from redis import Redis


class ToolRegistry:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.tools: Dict[str, Callable[..., Any]] = {
            "update_task_status": self.update_task_status,
            "track_task_progress": self.track_task_progress,
            "get_user_context": self.get_user_context,
            "submit_eda_job": self.submit_eda_job,
            "get_eda_result": self.get_eda_result,
            "read_artifact": self.read_artifact,
            "write_artifact": self.write_artifact,
        }

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
        return {"job_id": f"mock-{task_id}-{stage.lower()}", "status": "queued"}

    def get_eda_result(self, task_id: str, stage: str, payload: Dict[str, Any]):
        return {"task_id": task_id, "stage": stage, "status": "completed", "summary": "Mock EDA result"}

    def read_artifact(self, task_id: str, stage: str, payload: Dict[str, Any]):
        path = payload.get("path", "")
        return self.redis.get(f"artifact:{task_id}:{path}") or ""

    def write_artifact(self, task_id: str, stage: str, payload: Dict[str, Any]):
        path = payload.get("path", f"reports/{stage.lower()}.md")
        content = payload.get("content", payload.get("summary", ""))
        self.redis.set(f"artifact:{task_id}:{path}", content)
        self.redis.hset(f"artifact:index:{task_id}", path, stage)
        return {"status": "written", "path": path}
