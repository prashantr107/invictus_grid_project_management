from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.db.session import get_db
from app.models import User
from app.schemas import UserCreate, UserPage, UserRead, UserRoleUpdate, UserStatusUpdate
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db), actor: User = Depends(require_admin)) -> User:
    return users_service.create_user(db, actor, payload)


@router.get("", response_model=UserPage)
def list_users(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=160),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserPage:
    items, total = users_service.list_users(db, offset=offset, limit=limit, search=search)
    return UserPage(items=items, total=total, offset=offset, limit=limit)


@router.patch("/{user_id}/status", response_model=UserRead)
def update_user_status(
    user_id: UUID, payload: UserStatusUpdate, db: Session = Depends(get_db), actor: User = Depends(require_admin)
) -> User:
    return users_service.set_active(db, actor, user_id, payload.is_active)


@router.patch("/{user_id}/role", response_model=UserRead)
def update_user_role(
    user_id: UUID, payload: UserRoleUpdate, db: Session = Depends(get_db), actor: User = Depends(require_admin)
) -> User:
    return users_service.change_role(db, actor, user_id, payload.role)
