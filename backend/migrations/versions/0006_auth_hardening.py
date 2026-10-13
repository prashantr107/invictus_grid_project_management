"""Auth hardening: refresh-token families and account lockout counters.

Adds `auth_sessions.family_id` (rotation-family id used for reuse detection)
and `users.failed_login_attempts` / `users.locked_until` (per-account lockout).
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_auth_hardening"
down_revision = "0005_audit_target_uuid_task_status_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))

    op.add_column("auth_sessions", sa.Column("family_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE auth_sessions SET family_id = id WHERE family_id IS NULL")
    with op.batch_alter_table("auth_sessions") as batch_op:
        batch_op.alter_column("family_id", existing_type=sa.Uuid(), nullable=False)
    op.create_index("ix_auth_sessions_family_id", "auth_sessions", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_family_id", table_name="auth_sessions")
    with op.batch_alter_table("auth_sessions") as batch_op:
        batch_op.drop_column("family_id")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
