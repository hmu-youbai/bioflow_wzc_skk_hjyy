from __future__ import annotations
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

class TaskState(str, Enum):
    PENDING = "PENDING"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FINALIZING = "FINALIZING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"
    KILLED = "KILLED"
    TIMEOUT = "TIMEOUT"
    OOM = "OOM"

@dataclass
class ResourceLimits:
    cpu_time_sec: float | None = None
    wall_time_sec: float | None = None
    memory_mb: int | None = None
    max_processes: int | None = None

@dataclass
class TaskEvent:
    ts: float
    type: str
    data: dict[str, Any] = field(default_factory=dict)

@dataclass
class TaskRecord:
    task_id: str
    cmd: list[str]
    limits: ResourceLimits
    use_isolate: bool
    state: TaskState = TaskState.PENDING
    backend: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    ended_at: float | None = None
    finalized_at: float | None = None
    stop_requested: bool = False
    stop_requested_at: float | None = None
    root_pid: int | None = None
    exit_code: int | None = None
    exit_signal: int | None = None
    exit_reason: str | None = None
    killed_by: str | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None
    meta_path: str | None = None
    sandbox_dir: str | None = None
    last_seen_at: float | None = None
    last_snapshot_at: float | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    finalized: bool = False
    events: list[TaskEvent] = field(default_factory=list)

    def add_event(self, event_type: str, **data: Any) -> TaskEvent:
        event = TaskEvent(ts=time.time(), type=event_type, data=data)
        self.events.append(event)
        return event

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskRecord":
        payload = data.copy()
        payload["state"] = TaskState(payload["state"])
        payload["limits"] = ResourceLimits(**payload["limits"])
        payload["events"] = [TaskEvent(**e) for e in payload.get("events", [])]
        return cls(**payload)
