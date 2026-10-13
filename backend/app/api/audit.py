from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.db.session import get_db
from app.models import User
from app.schemas import AuditLogPage
from app.services import audit as audit_service

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=AuditLogPage)
def list_audit_logs(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> AuditLogPage:
    return audit_service.list_audit_logs(db, offset=offset, limit=limit)
