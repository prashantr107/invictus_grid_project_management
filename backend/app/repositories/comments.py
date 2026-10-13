"""Queries for task comments."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Comment


def get(db: Session, comment_id: UUID) -> Comment | None:
    return db.get(Comment, comment_id)


def list_for_task(db: Session, task_id: UUID) -> list[Comment]:
    return list(db.scalars(select(Comment).where(Comment.task_id == task_id).order_by(Comment.created_at.asc())).all())
