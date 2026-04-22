from __future__ import annotations
import os, shlex, shutil, signal, subprocess, threading, time, uuid
from pathlib import Path
import psutil
from app.domain.models import ResourceLimits, TaskRecord, TaskState
from app.repositories.base import TaskRepository

def parse_meta_file(path: str | None) -> dict[str, str]:
    if not path or not os.path.exists(path):
        return {}
    data = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip()
    return data

def read_tail(path: str | None, max_lines: int = 50) -> str:
    if not path or not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return "".join(lines[-max_lines:])

def safe_killpg(pid: int, sig: int = signal.SIGKILL) -> None:
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass

def kill_proc_tree(root_pid: int) -> None:
    try:
        parent = psutil.Process(root_pid)
    except psutil.NoSuchProcess:
        return
    for child in parent.children(recursive=True):
        try:
            child.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    try:
        parent.kill()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

def collect_tree_metrics(root_pid: int) -> dict:
    try:
        root = psutil.Process(root_pid)
    except psutil.NoSuchProcess:
        return {"cpu_percent": 0.0, "rss_mb": 0.0, "processes": 0, "threads": 0}
    procs = [root] + root.children(recursive=True)
    cpu = 0.0
    rss = 0
    proc_count = 0
    thread_count = 0
    for p in procs:
        try:
            proc_count += 1
            thread_count += p.num_threads()
            rss += p.memory_info().rss
            cpu += p.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return {"cpu_percent": cpu, "rss_mb": round(rss / 1024 / 1024, 2), "processes": proc_count, "threads": thread_count}

def resolve_final_state(rec: TaskRecord, meta: dict | None = None) -> tuple[TaskState, str]:
    meta = meta or {}
    if rec.stop_requested:
        return TaskState.KILLED, "stop requested"
    if meta.get("cg-oom-killed") == "1":
        return TaskState.OOM, "cgroup oom killed"
    if meta.get("status") == "TO":
        return TaskState.TIMEOUT, "backend timeout"
    if rec.exit_reason == "soft wall timeout":
        return TaskState.TIMEOUT, "soft wall timeout"
    if rec.exit_reason == "soft memory exceeded":
        return TaskState.OOM, "soft memory exceeded"
    if rec.exit_reason == "soft process/thread exceeded":
        return TaskState.FAILED, "soft process/thread exceeded"
    if rec.exit_code == 0:
        return TaskState.FINISHED, "process exited normally"
    return TaskState.FAILED, f"process exited with code {rec.exit_code}"

class SandboxManager:
    def __init__(self, repository: TaskRepository, isolate_bin: str = "isolate", work_root: str = "/tmp/sandbox_service") -> None:
        self.lock = threading.RLock()
        self.tasks = {}
        self.repo = repository
        self.isolate_bin = isolate_bin
        self.work_root = Path(work_root)
        self.work_root.mkdir(parents=True, exist_ok=True)
        for rec in self.repo.list_tasks(limit=1000):
            self.tasks[rec.task_id] = rec

    def isolate_available(self) -> bool:
        return shutil.which(self.isolate_bin) is not None

    def start_task(self, cmd: list[str], limits: ResourceLimits, use_isolate: bool = True) -> str:
        task_id = uuid.uuid4().hex[:12]
        rec = TaskRecord(task_id=task_id, cmd=cmd, limits=limits, use_isolate=use_isolate)
        rec.add_event("created", cmd=cmd, use_isolate=use_isolate)
        with self.lock:
            self.tasks[task_id] = rec
            self.repo.save_task(rec)
        threading.Thread(target=self._run_task, args=(task_id,), daemon=True).start()
        return task_id

    def stop_task(self, task_id: str) -> None:
        with self.lock:
            rec = self.tasks.get(task_id)
            if rec is None:
                raise KeyError(task_id)
            rec.stop_requested = True
            rec.stop_requested_at = time.time()
            rec.add_event("stop_requested")
            self.repo.update_task(rec)

    def get_task(self, task_id: str) -> TaskRecord:
        with self.lock:
            rec = self.tasks.get(task_id)
            if rec is None:
                raise KeyError(task_id)
            return rec

    def list_tasks(self, limit: int = 100, state: str | None = None) -> list[dict]:
        with self.lock:
            records = sorted(self.tasks.values(), key=lambda x: x.created_at, reverse=True)
            if state:
                records = [r for r in records if r.state.value == state]
            records = records[:limit]
            return [{"task_id": r.task_id, "state": r.state.value, "backend": r.backend, "created_at": r.created_at, "started_at": r.started_at, "ended_at": r.ended_at, "exit_reason": r.exit_reason} for r in records]

    def _persist(self, rec: TaskRecord) -> None:
        self.repo.update_task(rec)

    def _run_task(self, task_id: str) -> None:
        with self.lock:
            rec = self.tasks[task_id]
            rec.state = TaskState.STARTING
            rec.add_event("state_changed", state=rec.state.value)
            self._persist(rec)
        try:
            if rec.use_isolate and self.isolate_available():
                self._run_isolate(task_id)
            else:
                self._run_local(task_id)
        except Exception as e:
            with self.lock:
                rec = self.tasks[task_id]
                rec.state = TaskState.FAILED
                rec.error = str(e)
                rec.ended_at = time.time()
                rec.add_event("exception", error=str(e))
                self._persist(rec)

    def _run_local(self, task_id: str) -> None:
        with self.lock:
            rec = self.tasks[task_id]
        task_dir = self.work_root / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = str(task_dir / "stdout.txt")
        stderr_path = str(task_dir / "stderr.txt")
        stdout_f = open(stdout_path, "w", encoding="utf-8")
        stderr_f = open(stderr_path, "w", encoding="utf-8")
        proc = subprocess.Popen(rec.cmd, stdout=stdout_f, stderr=stderr_f, text=True, start_new_session=True)
        with self.lock:
            rec = self.tasks[task_id]
            rec.backend = "local"
            rec.root_pid = proc.pid
            rec.stdout_path = stdout_path
            rec.stderr_path = stderr_path
            rec.started_at = time.time()
            rec.state = TaskState.RUNNING
            rec.add_event("started", pid=proc.pid, backend="local")
            rec.add_event("state_changed", state=rec.state.value)
            self._persist(rec)
        self._monitor_loop(task_id, proc)
        rc = proc.wait()
        stdout_f.close()
        stderr_f.close()
        with self.lock:
            rec = self.tasks[task_id]
            rec.exit_code = rc
            if rc is not None and rc < 0:
                rec.exit_signal = -rc
            rec.ended_at = time.time()
            rec.add_event("exited", returncode=rc)
            self._persist(rec)
        self._finalize_task(task_id, meta=None)

    def _run_isolate(self, task_id: str) -> None:
        with self.lock:
            rec = self.tasks[task_id]
        task_dir = self.work_root / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = str(task_dir / "stdout.txt")
        stderr_path = str(task_dir / "stderr.txt")
        meta_path = str(task_dir / "meta.txt")
        box_id = int(task_id[-4:], 16) % 8000 + 1000
        init_cmd = [self.isolate_bin, "--cg", f"--box-id={box_id}", "--init"]
        init_proc = subprocess.run(init_cmd, capture_output=True, text=True, check=True)
        sandbox_dir = init_proc.stdout.strip()
        box_dir = Path(sandbox_dir) / "box"
        box_dir.mkdir(parents=True, exist_ok=True)
        launcher = box_dir / "launcher.sh"
        launcher.write_text("#!/usr/bin/env bash\nset -euo pipefail\ncd /box\n" + " ".join(shlex.quote(x) for x in rec.cmd) + "\n", encoding="utf-8")
        os.chmod(launcher, 0o755)
        run_cmd = [self.isolate_bin, "--cg", f"--box-id={box_id}", f"--meta={meta_path}", f"--stdout={stdout_path}", f"--stderr={stderr_path}", "--chdir=/box"]
        if rec.limits.cpu_time_sec is not None:
            run_cmd.append(f"--time={rec.limits.cpu_time_sec}")
        if rec.limits.wall_time_sec is not None:
            run_cmd.append(f"--wall-time={rec.limits.wall_time_sec}")
        if rec.limits.memory_mb is not None:
            run_cmd.append(f"--cg-mem={rec.limits.memory_mb * 1024}")
        if rec.limits.max_processes is not None:
            run_cmd.append(f"--processes={rec.limits.max_processes}")
        run_cmd.extend(["--run", "--", "/bin/bash", "launcher.sh"])
        proc = subprocess.Popen(run_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
        with self.lock:
            rec = self.tasks[task_id]
            rec.backend = "isolate"
            rec.root_pid = proc.pid
            rec.stdout_path = stdout_path
            rec.stderr_path = stderr_path
            rec.meta_path = meta_path
            rec.sandbox_dir = sandbox_dir
            rec.started_at = time.time()
            rec.state = TaskState.RUNNING
            rec.add_event("started", pid=proc.pid, backend="isolate")
            rec.add_event("state_changed", state=rec.state.value)
            self._persist(rec)
        self._monitor_loop(task_id, proc)
        rc = proc.wait()
        meta = parse_meta_file(meta_path)
        with self.lock:
            rec = self.tasks[task_id]
            rec.exit_code = rc
            if rc is not None and rc < 0:
                rec.exit_signal = -rc
            rec.ended_at = time.time()
            rec.add_event("exited", returncode=rc, meta=meta)
            self._persist(rec)
        self._finalize_task(task_id, meta=meta)
        subprocess.run([self.isolate_bin, "--cg", f"--box-id={box_id}", "--cleanup"], capture_output=True, text=True)

    def _monitor_loop(self, task_id: str, proc: subprocess.Popen) -> None:
        root_pid = proc.pid
        try:
            root = psutil.Process(root_pid)
            root.cpu_percent(interval=None)
            for c in root.children(recursive=True):
                c.cpu_percent(interval=None)
        except Exception:
            pass
        while True:
            time.sleep(0.2)
            with self.lock:
                rec = self.tasks[task_id]
            if proc.poll() is not None:
                break
            try:
                p = psutil.Process(root_pid)
                if (not p.is_running()) or p.status() == psutil.STATUS_ZOMBIE:
                    break
            except psutil.NoSuchProcess:
                break
            metrics = collect_tree_metrics(root_pid)
            now = time.time()
            metrics["wall_time_sec"] = round(now - (rec.started_at or now), 3)
            metrics["sample_time"] = now
            if rec.meta_path:
                metrics["meta"] = parse_meta_file(rec.meta_path)
            with self.lock:
                rec = self.tasks[task_id]
                rec.metrics = metrics
                rec.last_seen_at = now
                rec.last_snapshot_at = now
                self._persist(rec)
            if rec.stop_requested:
                with self.lock:
                    rec.state = TaskState.STOPPING
                    rec.killed_by = "user"
                    rec.add_event("state_changed", state=rec.state.value)
                    self._persist(rec)
                safe_killpg(root_pid, signal.SIGKILL)
                kill_proc_tree(root_pid)
                break
            if rec.backend == "local":
                if rec.limits.wall_time_sec is not None and metrics["wall_time_sec"] > rec.limits.wall_time_sec:
                    with self.lock:
                        rec.exit_reason = "soft wall timeout"
                        rec.killed_by = "monitor"
                        rec.add_event("limit_hit", reason=rec.exit_reason)
                        self._persist(rec)
                    safe_killpg(root_pid, signal.SIGKILL)
                    kill_proc_tree(root_pid)
                    break
                if rec.limits.memory_mb is not None and metrics["rss_mb"] > rec.limits.memory_mb:
                    with self.lock:
                        rec.exit_reason = "soft memory exceeded"
                        rec.killed_by = "monitor"
                        rec.add_event("limit_hit", reason=rec.exit_reason)
                        self._persist(rec)
                    safe_killpg(root_pid, signal.SIGKILL)
                    kill_proc_tree(root_pid)
                    break
                if rec.limits.max_processes is not None and max(metrics["processes"], metrics["threads"]) > rec.limits.max_processes:
                    with self.lock:
                        rec.exit_reason = "soft process/thread exceeded"
                        rec.killed_by = "monitor"
                        rec.add_event("limit_hit", reason=rec.exit_reason)
                        self._persist(rec)
                    safe_killpg(root_pid, signal.SIGKILL)
                    kill_proc_tree(root_pid)
                    break

    def _finalize_task(self, task_id: str, meta: dict | None) -> None:
        with self.lock:
            rec = self.tasks[task_id]
            rec.state = TaskState.FINALIZING
            rec.add_event("state_changed", state=rec.state.value)
            self._persist(rec)
        final_state, reason = resolve_final_state(rec, meta)
        with self.lock:
            rec = self.tasks[task_id]
            rec.state = final_state
            rec.finalized = True
            rec.finalized_at = time.time()
            rec.exit_reason = rec.exit_reason or reason
            rec.result = {"meta": meta or {}, "stdout_tail": read_tail(rec.stdout_path), "stderr_tail": read_tail(rec.stderr_path)}
            rec.add_event("finalized", state=rec.state.value, reason=rec.exit_reason)
            self._persist(rec)
