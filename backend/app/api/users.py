from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.db.session import get_db
from app.models import User
from app.schemas import (
    PasswordReset,
    UserCreate,
    UserPage,
    UserProfileUpdate,
    UserRead,
    UserRoleUpdate,
    UserStatusUpdate,
)
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserRead)
def update_my_profile(
    payload: UserProfileUpdate, db: Session = Depends(get_db), actor: User = Depends(get_current_user)
) -> User:
    return users_service.update_profile(db, actor, payload)


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> User:
    return users_service.get_user(db, user_id)


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


@router.post("/{user_id}/password-reset", response_model=UserRead)
def reset_user_password(
    user_id: UUID, payload: PasswordReset, db: Session = Depends(get_db), actor: User = Depends(require_admin)
) -> User:
    return users_service.reset_password(db, actor, user_id, payload.new_password.get_secret_value())
