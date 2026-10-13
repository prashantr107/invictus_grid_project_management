"""Read access to the Admin-only audit log (SRS §3.12)."""

from sqlalchemy.orm import Session

from app.repositories import audit as audit_repo
from app.repositories import tasks as tasks_repo
from app.schemas import AuditLogPage, AuditLogRead


def list_audit_logs(db: Session, *, offset: int, limit: int) -> AuditLogPage:
    entries, total = audit_repo.list_page(db, offset=offset, limit=limit)
    actor_ids = {entry.actor_id for entry in entries if entry.actor_id is not None}
    names = tasks_repo.names(db, actor_ids)
    items = [
        AuditLogRead(
            id=entry.id,
            actor_id=entry.actor_id,
            actor_name=names.get(entry.actor_id),
            action=entry.action,
            target_type=entry.target_type,
            target_id=entry.target_id,
            details=entry.details or {},
            created_at=entry.created_at,
        )
        for entry in entries
    ]
    return AuditLogPage(items=items, total=total, offset=offset, limit=limit)
