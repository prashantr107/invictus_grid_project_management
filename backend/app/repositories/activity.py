"""Queries for the activity feed."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ActivityLog


def list_page(
    db: Session, *, project_id: UUID | None, task_id: UUID | None, offset: int, limit: int
) -> tuple[list[ActivityLog], int]:
    statement = select(ActivityLog)
    count_statement = select(func.count()).select_from(ActivityLog)
    if project_id is not None:
        statement = statement.where(ActivityLog.project_id == project_id)
        count_statement = count_statement.where(ActivityLog.project_id == project_id)
    if task_id is not None:
        statement = statement.where(ActivityLog.task_id == task_id)
        count_statement = count_statement.where(ActivityLog.task_id == task_id)
    items = list(db.scalars(statement.order_by(ActivityLog.created_at.desc()).offset(offset).limit(limit)).all())
    total = db.scalar(count_statement) or 0
    return items, total
