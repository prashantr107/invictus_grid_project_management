from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.db.session import get_db
from app.models import User
from app.schemas import (
    ProjectCreate,
    ProjectMembershipRead,
    ProjectMembershipReplace,
    ProjectPage,
    ProjectRead,
)
from app.services import projects as projects_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> ProjectRead:
    return projects_service.create_project(db, actor, payload)


@router.get("", response_model=ProjectPage)
def list_projects(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=180),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> ProjectPage:
    return projects_service.list_projects(db, actor, offset=offset, limit=limit, search=search)


@router.get("/{project_id}/members", response_model=ProjectMembershipRead)
def get_project_members(
    project_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> ProjectMembershipRead:
    return projects_service.get_members(db, actor, project_id)


@router.put("/{project_id}/members", response_model=ProjectMembershipRead)
def replace_project_members(
    project_id: UUID,
    payload: ProjectMembershipReplace,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> ProjectMembershipRead:
    return projects_service.replace_members(db, actor, project_id, payload)
