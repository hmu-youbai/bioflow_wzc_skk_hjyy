from __future__ import annotations
from sqlalchemy import Boolean, Column, Float, Integer, MetaData, String, Table, Text, Index

metadata = MetaData()

tasks = Table(
    "tasks", metadata,
    Column("task_id", String(64), primary_key=True),
    Column("state", String(32), nullable=False, index=True),
    Column("backend", String(32), nullable=False, default=""),
    Column("cmd_json", Text, nullable=False),
    Column("limits_json", Text, nullable=False),
    Column("use_isolate", Boolean, nullable=False, default=True),
    Column("stop_requested", Boolean, nullable=False, default=False),
    Column("stop_requested_at", Float, nullable=True),
    Column("created_at", Float, nullable=False, index=True),
    Column("started_at", Float, nullable=True),
    Column("ended_at", Float, nullable=True),
    Column("finalized_at", Float, nullable=True),
    Column("root_pid", Integer, nullable=True),
    Column("exit_code", Integer, nullable=True),
    Column("exit_signal", Integer, nullable=True),
    Column("exit_reason", String(255), nullable=True),
    Column("killed_by", String(64), nullable=True),
    Column("stdout_path", Text, nullable=True),
    Column("stderr_path", Text, nullable=True),
    Column("meta_path", Text, nullable=True),
    Column("sandbox_dir", Text, nullable=True),
    Column("last_seen_at", Float, nullable=True),
    Column("last_snapshot_at", Float, nullable=True),
    Column("metrics_json", Text, nullable=False, default="{}"),
    Column("result_json", Text, nullable=False, default="{}"),
    Column("error", Text, nullable=True),
    Column("finalized", Boolean, nullable=False, default=False),
    Column("updated_at", Float, nullable=False),
)

task_events = Table(
    "task_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("task_id", String(64), nullable=False, index=True),
    Column("event_ts", Float, nullable=False, index=True),
    Column("event_type", String(64), nullable=False, index=True),
    Column("event_data_json", Text, nullable=False, default="{}"),
)

Index("ix_task_events_task_ts", task_events.c.task_id, task_events.c.event_ts)
