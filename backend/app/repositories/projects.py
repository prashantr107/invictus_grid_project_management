"""Queries for the projects aggregate (projects, membership, progress)."""

from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models import Project, ProjectMember, Task, TaskStatus, User


def get(db: Session, project_id: UUID) -> Project | None:
    return db.get(Project, project_id)


def get_for_update(db: Session, project_id: UUID) -> Project | None:
    return db.scalar(select(Project).where(Project.id == project_id).with_for_update())


def list_page(
    db: Session, *, actor_id: UUID, is_admin: bool, offset: int, limit: int, search: str | None
) -> tuple[list[Project], int]:
    statement = select(Project)
    count_statement = select(func.count()).select_from(Project)
    if not is_admin:
        statement = statement.join(ProjectMember, ProjectMember.project_id == Project.id).where(
            ProjectMember.user_id == actor_id
        )
        count_statement = count_statement.join(ProjectMember, ProjectMember.project_id == Project.id).where(
            ProjectMember.user_id == actor_id
        )
    if search and search.strip():
        term = f"%{search.strip()}%"
        criteria = or_(Project.key.ilike(term), Project.name.ilike(term))
        statement = statement.where(criteria)
        count_statement = count_statement.where(criteria)
    projects = list(db.scalars(statement.order_by(Project.created_at.desc()).offset(offset).limit(limit)).all())
    total = db.scalar(count_statement) or 0
    return projects, total


def member_counts(db: Session, project_ids: list[UUID]) -> dict[UUID, dict[str, int]]:
    counts = {project_id: {"MANAGER": 0, "MEMBER": 0} for project_id in project_ids}
    if not project_ids:
        return counts
    rows = db.execute(
        select(ProjectMember.project_id, ProjectMember.role, func.count())
        .where(ProjectMember.project_id.in_(project_ids))
        .group_by(ProjectMember.project_id, ProjectMember.role)
    )
    for project_id, role, count in rows:
        counts[project_id][role] = count
    return counts


def progress(db: Session, project_ids: list[UUID]) -> dict[UUID, int]:
    """SRS §3.11: completed tasks / total tasks * 100, 0 when empty.

    All tasks are "active" (there is no cancelled state), so the denominator is
    every task in the project.
    """
    result = {project_id: 0 for project_id in project_ids}
    if not project_ids:
        return result
    completed = func.sum(case((Task.status == TaskStatus.COMPLETED.value, 1), else_=0))
    rows = db.execute(
        select(Task.project_id, func.count(), completed)
        .where(Task.project_id.in_(project_ids))
        .group_by(Task.project_id)
    )
    for project_id, total, done in rows:
        result[project_id] = round(int(done) / total * 100) if total else 0
    return result


def membership(db: Session, project_id: UUID, user_id: UUID) -> ProjectMember | None:
    return db.get(ProjectMember, (project_id, user_id))


def memberships(db: Session, project_id: UUID) -> list[ProjectMember]:
    return list(db.scalars(select(ProjectMember).where(ProjectMember.project_id == project_id)).all())


def members_with_users(db: Session, project_id: UUID) -> list[tuple[ProjectMember, User]]:
    rows = db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(User.full_name)
    ).all()
    return list(rows)
