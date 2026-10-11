"""Queries for the users aggregate."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import ProjectMember, User


def get(db: Session, user_id: UUID) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_many(db: Session, user_ids: list[UUID]) -> dict[UUID, User]:
    if not user_ids:
        return {}
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
    return {user.id: user for user in users}


def list_page(db: Session, *, offset: int, limit: int, search: str | None) -> tuple[list[User], int]:
    statement = select(User)
    count_statement = select(func.count()).select_from(User)
    if search and search.strip():
        term = f"%{search.strip()}%"
        criteria = or_(User.full_name.ilike(term), User.email.ilike(term))
        statement = statement.where(criteria)
        count_statement = count_statement.where(criteria)
    items = list(db.scalars(statement.order_by(User.created_at.desc()).offset(offset).limit(limit)).all())
    total = db.scalar(count_statement) or 0
    return items, total


def memberships_with_role(db: Session, user_id: UUID, role: str) -> list[ProjectMember]:
    return list(
        db.scalars(select(ProjectMember).where(ProjectMember.user_id == user_id, ProjectMember.role == role)).all()
    )
