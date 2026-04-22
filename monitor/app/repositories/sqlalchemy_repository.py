from __future__ import annotations
import json, time
from typing import Any
from sqlalchemy import create_engine, delete, insert, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from app.db.sqlalchemy_tables import metadata, task_events, tasks
from app.domain.models import ResourceLimits, TaskEvent, TaskRecord, TaskState

def _record_to_row(rec: TaskRecord) -> dict[str, Any]:
    return {
        "task_id": rec.task_id, "state": rec.state.value, "backend": rec.backend,
        "cmd_json": json.dumps(rec.cmd, ensure_ascii=False),
        "limits_json": json.dumps(rec.limits.__dict__, ensure_ascii=False),
        "use_isolate": rec.use_isolate, "stop_requested": rec.stop_requested,
        "stop_requested_at": rec.stop_requested_at, "created_at": rec.created_at,
        "started_at": rec.started_at, "ended_at": rec.ended_at, "finalized_at": rec.finalized_at,
        "root_pid": rec.root_pid, "exit_code": rec.exit_code, "exit_signal": rec.exit_signal,
        "exit_reason": rec.exit_reason, "killed_by": rec.killed_by,
        "stdout_path": rec.stdout_path, "stderr_path": rec.stderr_path, "meta_path": rec.meta_path,
        "sandbox_dir": rec.sandbox_dir, "last_seen_at": rec.last_seen_at,
        "last_snapshot_at": rec.last_snapshot_at,
        "metrics_json": json.dumps(rec.metrics, ensure_ascii=False),
        "result_json": json.dumps(rec.result, ensure_ascii=False),
        "error": rec.error, "finalized": rec.finalized, "updated_at": time.time(),
    }

def _row_to_record(row: Any, events: list[TaskEvent] | None = None) -> TaskRecord:
    limits = ResourceLimits(**json.loads(row["limits_json"]))
    return TaskRecord(
        task_id=row["task_id"], cmd=json.loads(row["cmd_json"]), limits=limits,
        use_isolate=bool(row["use_isolate"]), state=TaskState(row["state"]), backend=row["backend"] or "",
        created_at=row["created_at"], started_at=row["started_at"], ended_at=row["ended_at"],
        finalized_at=row["finalized_at"], stop_requested=bool(row["stop_requested"]),
        stop_requested_at=row["stop_requested_at"], root_pid=row["root_pid"], exit_code=row["exit_code"],
        exit_signal=row["exit_signal"], exit_reason=row["exit_reason"], killed_by=row["killed_by"],
        stdout_path=row["stdout_path"], stderr_path=row["stderr_path"], meta_path=row["meta_path"],
        sandbox_dir=row["sandbox_dir"], last_seen_at=row["last_seen_at"],
        last_snapshot_at=row["last_snapshot_at"], metrics=json.loads(row["metrics_json"] or "{}"),
        result=json.loads(row["result_json"] or "{}"), error=row["error"],
        finalized=bool(row["finalized"]), events=events or [],
    )

class SQLAlchemyTaskRepository:
    def __init__(self, database_url: str) -> None:
        self.engine: Engine = create_engine(database_url, future=True, pool_pre_ping=True)

    def create_schema(self) -> None:
        metadata.create_all(self.engine)

    def save_task(self, rec: TaskRecord) -> None:
        with Session(self.engine) as session:
            session.execute(insert(tasks).values(**_record_to_row(rec)))
            for event in rec.events:
                session.execute(insert(task_events).values(
                    task_id=rec.task_id, event_ts=event.ts, event_type=event.type,
                    event_data_json=json.dumps(event.data, ensure_ascii=False),
                ))
            session.commit()

    def update_task(self, rec: TaskRecord) -> None:
        with Session(self.engine) as session:
            session.execute(update(tasks).where(tasks.c.task_id == rec.task_id).values(**_record_to_row(rec)))
            session.execute(delete(task_events).where(task_events.c.task_id == rec.task_id))
            for event in rec.events:
                session.execute(insert(task_events).values(
                    task_id=rec.task_id, event_ts=event.ts, event_type=event.type,
                    event_data_json=json.dumps(event.data, ensure_ascii=False),
                ))
            session.commit()

    def get_task(self, task_id: str) -> TaskRecord | None:
        with Session(self.engine) as session:
            row = session.execute(select(tasks).where(tasks.c.task_id == task_id)).mappings().first()
        if row is None:
            return None
        return _row_to_record(row, events=self.list_events(task_id))

    def list_tasks(self, limit: int = 100, state: str | None = None) -> list[TaskRecord]:
        stmt = select(tasks).order_by(tasks.c.created_at.desc()).limit(limit)
        if state:
            stmt = stmt.where(tasks.c.state == state)
        with Session(self.engine) as session:
            rows = session.execute(stmt).mappings().all()
        return [_row_to_record(row, events=[]) for row in rows]

    def append_event(self, task_id: str, event: TaskEvent) -> None:
        with Session(self.engine) as session:
            session.execute(insert(task_events).values(
                task_id=task_id, event_ts=event.ts, event_type=event.type,
                event_data_json=json.dumps(event.data, ensure_ascii=False),
            ))
            session.commit()

    def list_events(self, task_id: str) -> list[TaskEvent]:
        with Session(self.engine) as session:
            rows = session.execute(
                select(task_events).where(task_events.c.task_id == task_id)
                .order_by(task_events.c.event_ts.asc(), task_events.c.id.asc())
            ).mappings().all()
        return [TaskEvent(ts=row["event_ts"], type=row["event_type"], data=json.loads(row["event_data_json"] or "{}")) for row in rows]

    def health_check(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
