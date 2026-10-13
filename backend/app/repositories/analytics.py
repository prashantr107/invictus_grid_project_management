"""Aggregate queries backing the project analytics/dashboard endpoint (SRS §3.11)."""

from datetime import date
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.models import ProjectMember, Task, TaskPriority, TaskStatus, User


def status_counts(db: Session, project_id: UUID) -> dict[str, int]:
    counts = {status.value: 0 for status in TaskStatus}
    rows = db.execute(select(Task.status, func.count()).where(Task.project_id == project_id).group_by(Task.status))
    for status, count in rows:
        counts[status] = count
    return counts


def priority_counts(db: Session, project_id: UUID) -> dict[str, int]:
    counts = {priority.value: 0 for priority in TaskPriority}
    rows = db.execute(select(Task.priority, func.count()).where(Task.project_id == project_id).group_by(Task.priority))
    for priority, count in rows:
        counts[priority] = count
    return counts


def overdue_count(db: Session, project_id: UUID, *, today: date) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Task)
            .where(
                Task.project_id == project_id,
                Task.due_date.is_not(None),
                Task.due_date < today,
                Task.status != TaskStatus.COMPLETED.value,
            )
        )
        or 0
    )


def contributions(db: Session, project_id: UUID, *, today: date) -> list[dict]:
    """Per-member task metrics for every member/manager on the project.

    Members with no assigned tasks are still returned (zero counts) so the
    dashboard reflects the whole team."""
    completed = func.sum(case((Task.status == TaskStatus.COMPLETED.value, 1), else_=0))
    pending = func.sum(case((Task.status == TaskStatus.PENDING_REVIEW.value, 1), else_=0))
    changes = func.sum(case((Task.status == TaskStatus.CHANGES_REQUIRED.value, 1), else_=0))
    overdue = func.sum(
        case(
            (
                and_(
                    Task.due_date.is_not(None),
                    Task.due_date < today,
                    Task.status != TaskStatus.COMPLETED.value,
                ),
                1,
            ),
            else_=0,
        )
    )
    rows = db.execute(
        select(
            ProjectMember.user_id,
            User.full_name,
            ProjectMember.role,
            func.count(Task.id),
            completed,
            pending,
            changes,
            overdue,
        )
        .join(User, User.id == ProjectMember.user_id)
        .outerjoin(
            Task,
            and_(Task.project_id == ProjectMember.project_id, Task.assignee_id == ProjectMember.user_id),
        )
        .where(ProjectMember.project_id == project_id)
        .group_by(ProjectMember.user_id, User.full_name, ProjectMember.role)
        .order_by(User.full_name)
    )
    return [
        {
            "user_id": user_id,
            "full_name": full_name,
            "role": role,
            "assigned": assigned,
            "completed": int(done or 0),
            "pending_review": int(pending_review or 0),
            "changes_required": int(changes_required or 0),
            "overdue": int(overdue_count or 0),
        }
        for user_id, full_name, role, assigned, done, pending_review, changes_required, overdue_count in rows
    ]
