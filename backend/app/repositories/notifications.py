"""Queries for the notifications inbox."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Notification


def get(db: Session, notification_id: UUID) -> Notification | None:
    return db.get(Notification, notification_id)


def list_page(
    db: Session, recipient_id: UUID, *, unread_only: bool, offset: int, limit: int
) -> tuple[list[Notification], int]:
    statement = select(Notification).where(Notification.recipient_id == recipient_id)
    count_statement = select(func.count()).select_from(Notification).where(Notification.recipient_id == recipient_id)
    if unread_only:
        statement = statement.where(Notification.is_read.is_(False))
        count_statement = count_statement.where(Notification.is_read.is_(False))
    items = list(db.scalars(statement.order_by(Notification.created_at.desc()).offset(offset).limit(limit)).all())
    total = db.scalar(count_statement) or 0
    return items, total


def unread_count(db: Session, recipient_id: UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.recipient_id == recipient_id, Notification.is_read.is_(False))
        )
        or 0
    )
