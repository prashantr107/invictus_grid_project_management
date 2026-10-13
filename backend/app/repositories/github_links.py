"""Queries for GitHub evidence links on tasks."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GithubLink


def get(db: Session, link_id: UUID) -> GithubLink | None:
    return db.get(GithubLink, link_id)


def list_for_task(db: Session, task_id: UUID) -> list[GithubLink]:
    return list(
        db.scalars(select(GithubLink).where(GithubLink.task_id == task_id).order_by(GithubLink.created_at.asc())).all()
    )
