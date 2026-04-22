"""init tasks and events"""
from alembic import op
import sqlalchemy as sa
revision = "0001_init_tasks_and_events"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("task_id", sa.String(length=64), primary_key=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("backend", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("cmd_json", sa.Text(), nullable=False),
        sa.Column("limits_json", sa.Text(), nullable=False),
        sa.Column("use_isolate", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("stop_requested", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("stop_requested_at", sa.Float(), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("started_at", sa.Float(), nullable=True),
        sa.Column("ended_at", sa.Float(), nullable=True),
        sa.Column("finalized_at", sa.Float(), nullable=True),
        sa.Column("root_pid", sa.Integer(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("exit_signal", sa.Integer(), nullable=True),
        sa.Column("exit_reason", sa.String(length=255), nullable=True),
        sa.Column("killed_by", sa.String(length=64), nullable=True),
        sa.Column("stdout_path", sa.Text(), nullable=True),
        sa.Column("stderr_path", sa.Text(), nullable=True),
        sa.Column("meta_path", sa.Text(), nullable=True),
        sa.Column("sandbox_dir", sa.Text(), nullable=True),
        sa.Column("last_seen_at", sa.Float(), nullable=True),
        sa.Column("last_snapshot_at", sa.Float(), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("result_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("finalized", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.Float(), nullable=False),
    )
    op.create_table(
        "task_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("event_ts", sa.Float(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_data_json", sa.Text(), nullable=False, server_default="{}"),
    )
