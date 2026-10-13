"""In-app notifications (SRS §3.10).

Other services call the `create*` helpers inside their own transaction; the
recipient-facing read/mark-read paths live here too."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import Notification, NotificationType, Role, User, utc_now
from app.repositories import notifications as notifications_repo
from app.repositories import projects as projects_repo
from app.schemas import NotificationPage, NotificationRead

_MESSAGES = {
    NotificationType.TASK_ASSIGNED.value: "You were assigned a task",
    NotificationType.REVIEW_REQUESTED.value: "A task is awaiting your review",
    NotificationType.CHANGES_REQUIRED.value: "Changes were requested on your task",
    NotificationType.TASK_APPROVED.value: "Your task was approved",
    NotificationType.PROJECT_ADDED.value: "You were added to a project",
}


def _read(notification: Notification) -> NotificationRead:
    return NotificationRead(
        id=notification.id,
        recipient_id=notification.recipient_id,
        type=notification.type,
        task_id=notification.task_id,
        project_id=notification.project_id,
        message=_MESSAGES.get(notification.type, "You have a notification"),
        is_read=notification.is_read,
        read_at=notification.read_at,
        created_at=notification.created_at,
    )


def create(
    db: Session,
    *,
    recipient_id: UUID,
    type: NotificationType,
    task_id: UUID | None = None,
    project_id: UUID | None = None,
) -> Notification:
    """Stage a notification; the calling service owns the commit."""
    notification = Notification(
        recipient_id=recipient_id,
        type=type.value,
        task_id=task_id,
        project_id=project_id,
    )
    db.add(notification)
    return notification


def notify_project_managers(
    db: Session,
    *,
    project_id: UUID,
    type: NotificationType,
    task_id: UUID | None = None,
    exclude_id: UUID | None = None,
) -> None:
    for membership in projects_repo.memberships(db, project_id):
        if membership.role == Role.MANAGER.value and membership.user_id != exclude_id:
            create(db, recipient_id=membership.user_id, type=type, task_id=task_id, project_id=project_id)


def list_notifications(db: Session, actor: User, *, unread_only: bool, offset: int, limit: int) -> NotificationPage:
    items, total = notifications_repo.list_page(db, actor.id, unread_only=unread_only, offset=offset, limit=limit)
    return NotificationPage(
        items=[_read(notification) for notification in items],
        total=total,
        unread=notifications_repo.unread_count(db, actor.id),
        offset=offset,
        limit=limit,
    )


def mark_read(db: Session, actor: User, notification_id: UUID) -> NotificationRead:
    notification = notifications_repo.get(db, notification_id)
    if notification is None or notification.recipient_id != actor.id:
        raise NotFoundError("Notification not found")
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = utc_now()
        db.commit()
        db.refresh(notification)
    return _read(notification)
