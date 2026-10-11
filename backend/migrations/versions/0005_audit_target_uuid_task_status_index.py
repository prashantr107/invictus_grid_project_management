"""Type audit_logs.target_id as UUID and index tasks.status."""

from alembic import op
import sqlalchemy as sa


revision = "0005_audit_target_uuid_task_status_index"
down_revision = "0004_collaboration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.alter_column(
            "target_id",
            existing_type=sa.String(length=80),
            type_=sa.Uuid(),
            existing_nullable=False,
            postgresql_using="target_id::uuid",
        )
    op.create_index("ix_tasks_status", "tasks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_tasks_status", table_name="tasks")
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.alter_column(
            "target_id",
            existing_type=sa.Uuid(),
            type_=sa.String(length=80),
            existing_nullable=False,
            postgresql_using="target_id::text",
        )
