from __future__ import annotations
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from app.domain.models import ResourceLimits
from app.repositories.factory import build_repository
from app.services.sandbox_manager import SandboxManager, read_tail
from app.settings import get_settings

settings = get_settings()
repo = build_repository(settings)
manager = SandboxManager(repository=repo, isolate_bin=settings.isolate_bin, work_root=settings.data_dir)
app = FastAPI(title="Sandbox Demo Service")

class LimitsIn(BaseModel):
    cpu_time_sec: float | None = None
    wall_time_sec: float | None = None
    memory_mb: int | None = None
    max_processes: int | None = None

class TaskCreateIn(BaseModel):
    cmd: list[str]
    limits: LimitsIn = LimitsIn()
    use_isolate: bool = True

@app.get("/health")
def health():
    return {"ok": True, "repository_type": settings.repository_type, "repository_healthy": repo.health_check()}

@app.post("/tasks")
def create_task(body: TaskCreateIn):
    limits = ResourceLimits(cpu_time_sec=body.limits.cpu_time_sec, wall_time_sec=body.limits.wall_time_sec, memory_mb=body.limits.memory_mb, max_processes=body.limits.max_processes)
    task_id = manager.start_task(body.cmd, limits, body.use_isolate)
    rec = manager.get_task(task_id)
    return {"task_id": task_id, "state": rec.state.value}

@app.get("/tasks")
def list_tasks(limit: int = Query(default=settings.list_tasks_default_limit, ge=1, le=1000), state: str | None = None):
    return manager.list_tasks(limit=limit, state=state)

@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    try:
        rec = manager.get_task(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="task not found")
    return {"task_id": rec.task_id, "state": rec.state.value, "backend": rec.backend, "created_at": rec.created_at, "started_at": rec.started_at, "ended_at": rec.ended_at, "finalized_at": rec.finalized_at, "root_pid": rec.root_pid, "exit_code": rec.exit_code, "exit_signal": rec.exit_signal, "exit_reason": rec.exit_reason, "error": rec.error, "finalized": rec.finalized}

@app.get("/tasks/{task_id}/metrics")
def get_metrics(task_id: str):
    try:
        rec = manager.get_task(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="task not found")
    return {"task_id": rec.task_id, "state": rec.state.value, "metrics": rec.metrics, "last_snapshot_at": rec.last_snapshot_at}

@app.get("/tasks/{task_id}/logs")
def get_logs(task_id: str):
    try:
        rec = manager.get_task(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="task not found")
    return {"stdout_tail": read_tail(rec.stdout_path), "stderr_tail": read_tail(rec.stderr_path), "result": rec.result}

@app.get("/tasks/{task_id}/events")
def get_events(task_id: str):
    try:
        rec = manager.get_task(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="task not found")
    return {"task_id": rec.task_id, "events": [{"ts": e.ts, "type": e.type, "data": e.data} for e in rec.events]}

@app.post("/tasks/{task_id}/stop")
def stop_task(task_id: str):
    try:
        manager.stop_task(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="task not found")
    return {"task_id": task_id, "status": "stop requested"}
