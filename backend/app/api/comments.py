from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas import CommentCreate, CommentRead
from app.services import collaboration as collaboration_service

router = APIRouter(prefix="/tasks/{task_id}/comments", tags=["comments"])


@router.get("", response_model=list[CommentRead])
def list_comments(
    task_id: UUID, db: Session = Depends(get_db), actor: User = Depends(get_current_user)
) -> list[CommentRead]:
    return collaboration_service.list_comments(db, actor, task_id)


@router.post("", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
def create_comment(
    task_id: UUID,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> CommentRead:
    return collaboration_service.create_comment(db, actor, task_id, payload)


@router.patch("/{comment_id}", response_model=CommentRead)
def update_comment(
    task_id: UUID,
    comment_id: UUID,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> CommentRead:
    return collaboration_service.update_comment(db, actor, task_id, comment_id, payload)


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    task_id: UUID,
    comment_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> None:
    collaboration_service.delete_comment(db, actor, task_id, comment_id)
