from __future__ import annotations
import time
from app.domain.models import ResourceLimits, TaskEvent, TaskRecord, TaskState

def repository_contract(repo) -> None:
    task = TaskRecord(task_id="contract-task-1", cmd=["echo", "hello"], limits=ResourceLimits(wall_time_sec=2), use_isolate=False, state=TaskState.PENDING)
    task.add_event("created", hello="world")
    repo.save_task(task)
    loaded = repo.get_task(task.task_id)
    assert loaded is not None
    assert loaded.task_id == task.task_id
    assert loaded.events[0].type == "created"
    loaded.state = TaskState.RUNNING
    loaded.started_at = time.time()
    loaded.add_event("started", pid=12345)
    repo.update_task(loaded)
    loaded2 = repo.get_task(task.task_id)
    assert loaded2 is not None
    assert loaded2.state == TaskState.RUNNING
    assert any(evt.type == "started" for evt in loaded2.events)
    repo.append_event(task.task_id, TaskEvent(ts=time.time(), type="custom", data={"x": 1}))
    events = repo.list_events(task.task_id)
    assert any(evt.type == "custom" for evt in events)
    tasks = repo.list_tasks(limit=10)
    assert any(t.task_id == task.task_id for t in tasks)
    running = repo.list_tasks(limit=10, state=TaskState.RUNNING.value)
    assert any(t.task_id == task.task_id for t in running)
    assert repo.health_check() is True
