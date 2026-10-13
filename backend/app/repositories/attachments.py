"""Queries for task attachments."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attachment


def get(db: Session, attachment_id: UUID) -> Attachment | None:
    return db.get(Attachment, attachment_id)


def list_for_task(db: Session, task_id: UUID) -> list[Attachment]:
    return list(
        db.scalars(select(Attachment).where(Attachment.task_id == task_id).order_by(Attachment.created_at.asc())).all()
    )
