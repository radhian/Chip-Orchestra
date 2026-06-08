"""Per-task run control: stop (pause) / resume / cancel.

A small thread-safe status registry the agent nodes consult at each step
boundary. Stop/cancel are cooperative — they take effect when the current node
(e.g. an in-flight LLM call) finishes, so no completed work is thrown away and
the run can be resumed from where it paused.
"""

from __future__ import annotations

import threading

RUNNING = "running"
STOPPING = "stopping"     # stop requested; node guard will pause at next boundary
PAUSED = "paused"         # run halted, resumable from its last checkpoint
CANCELLING = "cancelling"  # cancel requested
CANCELLED = "cancelled"

_lock = threading.Lock()
_status: dict[str, str] = {}


def set_status(task_id: str, status: str) -> None:
    with _lock:
        _status[task_id] = status


def get_status(task_id: str) -> str | None:
    with _lock:
        return _status.get(task_id)


def clear(task_id: str) -> None:
    with _lock:
        _status.pop(task_id, None)


class PipelineStopped(Exception):
    """Raised inside the graph to pause a run (resumable)."""


class PipelineCancelled(Exception):
    """Raised inside the graph to cancel a run (discarded)."""


def checkpoint(task_id: str) -> None:
    """Node guard: raise if a stop/cancel was requested for this task."""
    status = get_status(task_id)
    if status == CANCELLING:
        raise PipelineCancelled()
    if status == STOPPING:
        raise PipelineStopped()
