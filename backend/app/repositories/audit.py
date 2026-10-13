"""Queries for the Admin audit log viewer."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog


def list_page(db: Session, *, offset: int, limit: int) -> tuple[list[AuditLog], int]:
    statement = select(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    count_statement = select(func.count()).select_from(AuditLog)
    items = list(db.scalars(statement).all())
    total = db.scalar(count_statement) or 0
    return items, total
