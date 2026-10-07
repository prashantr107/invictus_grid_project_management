from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.core.security import hash_password
from app.db.session import get_db
from app.models import AuditLog, AuthSession, User, utc_now
from app.schemas import UserCreate, UserPage, UserRead, UserRoleUpdate, UserStatusUpdate

router = APIRouter(prefix="/users", tags=["users"])


def record_audit(db: Session, actor: User, action: str, target: User, details: dict) -> None:
    db.add(AuditLog(actor_id=actor.id, action=action, target_type="user", target_id=str(target.id), details=details))


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db), actor: User = Depends(require_admin)) -> User:
    user = User(
        email=str(payload.email).lower(), full_name=payload.full_name.strip(), role=payload.role.value,
        password_hash=hash_password(payload.initial_password.get_secret_value()), must_change_password=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A user with this email already exists") from None
    record_audit(db, actor, "user.created", user, {"role": user.role})
    db.commit()
    db.refresh(user)
    return user


@router.get("", response_model=UserPage)
def list_users(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=160),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserPage:
    statement = select(User)
    count_statement = select(func.count()).select_from(User)
    if search and search.strip():
        term = f"%{search.strip()}%"
        criteria = or_(User.full_name.ilike(term), User.email.ilike(term))
        statement = statement.where(criteria)
        count_statement = count_statement.where(criteria)
    items = list(db.scalars(statement.order_by(User.created_at.desc()).offset(offset).limit(limit)).all())
    total = db.scalar(count_statement) or 0
    return UserPage(items=items, total=total, offset=offset, limit=limit)


@router.patch("/{user_id}/status", response_model=UserRead)
def update_user_status(user_id: UUID, payload: UserStatusUpdate, db: Session = Depends(get_db), actor: User = Depends(require_admin)) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == actor.id and not payload.is_active:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    previous = user.is_active
    user.is_active = payload.is_active
    if previous and not payload.is_active:
        db.execute(
            AuthSession.__table__.update().where(
                AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)
            ).values(revoked_at=utc_now())
        )
    record_audit(db, actor, "user.activated" if payload.is_active else "user.deactivated", user, {"previous": previous})
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/role", response_model=UserRead)
def update_user_role(user_id: UUID, payload: UserRoleUpdate, db: Session = Depends(get_db), actor: User = Depends(require_admin)) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == actor.id and payload.role.value != "ADMIN":
        raise HTTPException(status_code=400, detail="You cannot remove your own Admin role")
    previous = user.role
    user.role = payload.role.value
    record_audit(db, actor, "user.role_changed", user, {"previous": previous, "new": user.role})
    db.commit()
    db.refresh(user)
    return user
