"""Read access to the activity feed for projects and tasks (SRS §3.12)."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import ActivityLog, User
from app.repositories import activity as activity_repo
from app.repositories import projects as projects_repo
from app.repositories import tasks as tasks_repo
from app.schemas import ActivityLogPage, ActivityLogRead
from app.services import permissions
from app.services import tasks as tasks_service


def _read(entry: ActivityLog, actor_name: str | None) -> ActivityLogRead:
    return ActivityLogRead(
        id=entry.id,
        project_id=entry.project_id,
        task_id=entry.task_id,
        actor_id=entry.actor_id,
        actor_name=actor_name,
        action=entry.action,
        details=entry.details or {},
        created_at=entry.created_at,
    )


def _page(db: Session, entries: list[ActivityLog], total: int, *, offset: int, limit: int) -> ActivityLogPage:
    actor_ids = {entry.actor_id for entry in entries if entry.actor_id is not None}
    names = tasks_repo.names(db, actor_ids)
    return ActivityLogPage(
        items=[_read(entry, names.get(entry.actor_id)) for entry in entries],
        total=total,
        offset=offset,
        limit=limit,
    )


def list_project_activity(db: Session, actor: User, project_id: UUID, *, offset: int, limit: int) -> ActivityLogPage:
    if projects_repo.get(db, project_id) is None:
        raise NotFoundError("Project not found")
    if permissions.project_role_for_user(db, project_id, actor) is None:
        raise NotFoundError("Project not found")
    entries, total = activity_repo.list_page(db, project_id=project_id, task_id=None, offset=offset, limit=limit)
    return _page(db, entries, total, offset=offset, limit=limit)


def list_task_activity(db: Session, actor: User, task_id: UUID, *, offset: int, limit: int) -> ActivityLogPage:
    task, _ = tasks_service.task_for_user(db, task_id, actor)
    entries, total = activity_repo.list_page(db, project_id=None, task_id=task.id, offset=offset, limit=limit)
    return _page(db, entries, total, offset=offset, limit=limit)
