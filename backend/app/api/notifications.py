from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas import NotificationPage, NotificationRead
from app.services import notifications as notifications_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationPage)
def list_notifications(
    unread_only: bool = Query(default=False),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> NotificationPage:
    return notifications_service.list_notifications(db, actor, unread_only=unread_only, offset=offset, limit=limit)


@router.patch("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    notification_id: UUID, db: Session = Depends(get_db), actor: User = Depends(get_current_user)
) -> NotificationRead:
    return notifications_service.mark_read(db, actor, notification_id)
