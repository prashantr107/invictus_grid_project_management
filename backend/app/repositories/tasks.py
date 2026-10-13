"""Queries for the tasks aggregate (tasks and reviews)."""

from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Task, TaskPriority, TaskReview, User

_PRIORITY_ORDER = case(
    {
        TaskPriority.LOW.value: 0,
        TaskPriority.MEDIUM.value: 1,
        TaskPriority.HIGH.value: 2,
        TaskPriority.URGENT.value: 3,
    },
    value=Task.priority,
    else_=0,
)

_SORT_ORDERS = {
    "created_desc": Task.created_at.desc(),
    "created_asc": Task.created_at.asc(),
    "due_date_asc": Task.due_date.asc().nulls_last(),
    "due_date_desc": Task.due_date.desc().nulls_last(),
    "priority_desc": _PRIORITY_ORDER.desc(),
    "priority_asc": _PRIORITY_ORDER.asc(),
    "title_asc": Task.title.asc(),
}


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
    sort: str | None = None,
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
    order_by = _SORT_ORDERS.get(sort or "created_desc", Task.created_at.desc())
    tasks = list(db.scalars(statement.order_by(order_by).offset(offset).limit(limit)).all())
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
