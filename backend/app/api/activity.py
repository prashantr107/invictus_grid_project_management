from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas import ActivityLogPage
from app.services import activity as activity_service

router = APIRouter(tags=["activity"])


@router.get("/projects/{project_id}/activity", response_model=ActivityLogPage)
def list_project_activity(
    project_id: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> ActivityLogPage:
    return activity_service.list_project_activity(db, actor, project_id, offset=offset, limit=limit)


@router.get("/tasks/{task_id}/activity", response_model=ActivityLogPage)
def list_task_activity(
    task_id: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> ActivityLogPage:
    return activity_service.list_task_activity(db, actor, task_id, offset=offset, limit=limit)
