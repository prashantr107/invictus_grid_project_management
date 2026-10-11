"""Queries for the tasks aggregate (tasks and reviews)."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Task, TaskReview, User


def get(db: Session, task_id: UUID) -> Task | None:
    return db.get(Task, task_id)


def max_issue_number(db: Session, project_id: UUID) -> int:
    return db.scalar(select(func.max(Task.issue_number)).where(Task.project_id == project_id)) or 0


def list_page(
    db: Session,
    *,
    project_id: UUID,
    assignee_scope: UUID | None,
    offset: int,
    limit: int,
    status: str | None,
    priority: str | None,
) -> tuple[list[Task], int]:
    statement = select(Task).where(Task.project_id == project_id)
    count_statement = select(func.count()).select_from(Task).where(Task.project_id == project_id)
    if assignee_scope is not None:
        statement = statement.where(Task.assignee_id == assignee_scope)
        count_statement = count_statement.where(Task.assignee_id == assignee_scope)
    if status:
        statement = statement.where(Task.status == status)
        count_statement = count_statement.where(Task.status == status)
    if priority:
        statement = statement.where(Task.priority == priority)
        count_statement = count_statement.where(Task.priority == priority)
    tasks = list(db.scalars(statement.order_by(Task.created_at.desc()).offset(offset).limit(limit)).all())
    total = db.scalar(count_statement) or 0
    return tasks, total


def names(db: Session, user_ids: set[UUID]) -> dict[UUID, str]:
    if not user_ids:
        return {}
    return dict(db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids))).all())


def reviews(db: Session, task_id: UUID) -> list[TaskReview]:
    return list(
        db.scalars(select(TaskReview).where(TaskReview.task_id == task_id).order_by(TaskReview.created_at.desc())).all()
    )
