from __future__ import annotations
import json
from pathlib import Path
from app.domain.models import TaskEvent, TaskRecord

class FileTaskRepository:
    def __init__(self, root: str = "/tmp/sandbox_service") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _task_dir(self, task_id: str) -> Path:
        return self.root / task_id

    def _task_json(self, task_id: str) -> Path:
        return self._task_dir(task_id) / "task.json"

    def save_task(self, rec: TaskRecord) -> None:
        self._task_dir(rec.task_id).mkdir(parents=True, exist_ok=True)
        self._write(rec)

    def update_task(self, rec: TaskRecord) -> None:
        self._task_dir(rec.task_id).mkdir(parents=True, exist_ok=True)
        self._write(rec)

    def get_task(self, task_id: str) -> TaskRecord | None:
        path = self._task_json(task_id)
        if not path.exists():
            return None
        return TaskRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_tasks(self, limit: int = 100, state: str | None = None) -> list[TaskRecord]:
        out = []
        for p in sorted(self.root.iterdir()):
            if not p.is_dir():
                continue
            task_file = p / "task.json"
            if not task_file.exists():
                continue
            try:
                rec = TaskRecord.from_dict(json.loads(task_file.read_text(encoding="utf-8")))
                if state and rec.state.value != state:
                    continue
                out.append(rec)
            except Exception:
                continue
        out.sort(key=lambda x: x.created_at, reverse=True)
        return out[:limit]

    def append_event(self, task_id: str, event: TaskEvent) -> None:
        rec = self.get_task(task_id)
        if rec is None:
            raise KeyError(task_id)
        rec.events.append(event)
        self.update_task(rec)

    def list_events(self, task_id: str) -> list[TaskEvent]:
        rec = self.get_task(task_id)
        if rec is None:
            raise KeyError(task_id)
        return rec.events

    def health_check(self) -> bool:
        try:
            probe = self.root / ".healthcheck"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except Exception:
            return False

    def _write(self, rec: TaskRecord) -> None:
        target = self._task_json(rec.task_id)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rec.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(target)
