"""Add comments, attachments, GitHub evidence, and notifications."""

from alembic import op
import sqlalchemy as sa


revision = "0004_collaboration"
down_revision = "0003_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comments_task_id", "comments", ["task_id"])
    op.create_index("ix_comments_author_id", "comments", ["author_id"])

    op.create_table(
        "attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("uploader_id", sa.Uuid(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=127), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("size_bytes >= 0", name="ck_attachments_size_non_negative"),
        sa.CheckConstraint(
            "content_type IN ('image/png', 'image/jpeg', 'application/pdf', "
            "'application/vnd.openxmlformats-officedocument.wordprocessingml.document')",
            name="ck_attachments_content_type",
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attachments_task_id", "attachments", ["task_id"])
    op.create_index("ix_attachments_uploader_id", "attachments", ["uploader_id"])
    op.create_index("ix_attachments_storage_key", "attachments", ["storage_key"], unique=True)

    op.create_table(
        "github_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("submitted_by", sa.Uuid(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("evidence_type", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "evidence_type IN ('REPOSITORY', 'COMMIT', 'PULL_REQUEST', 'OTHER')",
            name="ck_github_links_evidence_type",
        ),
        sa.CheckConstraint("url LIKE 'http%'", name="ck_github_links_url"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_github_links_task_id", "github_links", ["task_id"])
    op.create_index("ix_github_links_submitted_by", "github_links", ["submitted_by"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type IN ('TASK_ASSIGNED', 'REVIEW_REQUESTED', 'CHANGES_REQUIRED', 'TASK_APPROVED', 'PROJECT_ADDED')",
            name="ck_notifications_type",
        ),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_recipient_id", "notifications", ["recipient_id"])
    op.create_index("ix_notifications_task_id", "notifications", ["task_id"])
    op.create_index("ix_notifications_project_id", "notifications", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_project_id", table_name="notifications")
    op.drop_index("ix_notifications_task_id", table_name="notifications")
    op.drop_index("ix_notifications_recipient_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_github_links_submitted_by", table_name="github_links")
    op.drop_index("ix_github_links_task_id", table_name="github_links")
    op.drop_table("github_links")
    op.drop_index("ix_attachments_storage_key", table_name="attachments")
    op.drop_index("ix_attachments_uploader_id", table_name="attachments")
    op.drop_index("ix_attachments_task_id", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("ix_comments_author_id", table_name="comments")
    op.drop_index("ix_comments_task_id", table_name="comments")
    op.drop_table("comments")
