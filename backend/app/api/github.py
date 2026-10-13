from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas import GithubLinkCreate, GithubLinkRead
from app.services import collaboration as collaboration_service

router = APIRouter(prefix="/tasks/{task_id}/github-links", tags=["github-evidence"])


@router.get("", response_model=list[GithubLinkRead])
def list_github_links(
    task_id: UUID, db: Session = Depends(get_db), actor: User = Depends(get_current_user)
) -> list[GithubLinkRead]:
    return collaboration_service.list_github_links(db, actor, task_id)


@router.post("", response_model=GithubLinkRead, status_code=status.HTTP_201_CREATED)
def create_github_link(
    task_id: UUID,
    payload: GithubLinkCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> GithubLinkRead:
    return collaboration_service.create_github_link(db, actor, task_id, payload)


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_github_link(
    task_id: UUID,
    link_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> None:
    collaboration_service.delete_github_link(db, actor, task_id, link_id)
