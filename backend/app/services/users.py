"""User administration workflows (Admin-only): create, list, activate/
deactivate, and role changes with membership reconciliation."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.core.security import hash_password
from app.models import AuditLog, Role, User, utc_now
from app.repositories import sessions as sessions_repo
from app.repositories import users as users_repo
from app.schemas import UserCreate, UserProfileUpdate


def _record_audit(db: Session, actor: User, action: str, target: User, details: dict) -> None:
    db.add(AuditLog(actor_id=actor.id, action=action, target_type="user", target_id=target.id, details=details))


def create_user(db: Session, actor: User, payload: UserCreate) -> User:
    user = User(
        email=str(payload.email).lower(),
        full_name=payload.full_name.strip(),
        role=payload.role.value,
        password_hash=hash_password(payload.initial_password.get_secret_value()),
        must_change_password=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ConflictError("A user with this email already exists") from None
    _record_audit(db, actor, "user.created", user, {"role": user.role})
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session, *, offset: int, limit: int, search: str | None) -> tuple[list[User], int]:
    return users_repo.list_page(db, offset=offset, limit=limit, search=search)


def get_user(db: Session, user_id: UUID) -> User:
    user = users_repo.get(db, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user


def update_profile(db: Session, actor: User, payload: UserProfileUpdate) -> User:
    actor.full_name = payload.full_name
    _record_audit(db, actor, "user.profile_updated", actor, {})
    db.commit()
    db.refresh(actor)
    return actor


def set_active(db: Session, actor: User, user_id: UUID, is_active: bool) -> User:
    user = users_repo.get(db, user_id)
    if user is None:
        raise NotFoundError("User not found")
    if user.id == actor.id and not is_active:
        raise BadRequestError("You cannot deactivate your own account")
    previous = user.is_active
    user.is_active = is_active
    if previous and not is_active:
        sessions_repo.revoke_all_for_user(db, user.id)
    _record_audit(db, actor, "user.activated" if is_active else "user.deactivated", user, {"previous": previous})
    db.commit()
    db.refresh(user)
    return user


def change_role(db: Session, actor: User, user_id: UUID, role: Role) -> User:
    user = users_repo.get(db, user_id)
    if user is None:
        raise NotFoundError("User not found")
    if user.id == actor.id and role.value != Role.ADMIN.value:
        raise BadRequestError("You cannot remove your own Admin role")
    previous = user.role
    user.role = role.value
    details: dict = {"previous": previous, "new": user.role}
    if user.role == Role.MEMBER.value:
        downgraded = users_repo.memberships_with_role(db, user.id, Role.MANAGER.value)
        if downgraded:
            for membership in downgraded:
                membership.role = Role.MEMBER.value
                membership.added_by = actor.id
                membership.added_at = utc_now()
            details["memberships_downgraded_to_member"] = [str(membership.project_id) for membership in downgraded]
    _record_audit(db, actor, "user.role_changed", user, details)
    db.commit()
    db.refresh(user)
    return user


def reset_password(db: Session, actor: User, user_id: UUID, new_password: str) -> User:
    user = users_repo.get(db, user_id)
    if user is None:
        raise NotFoundError("User not found")
    user.password_hash = hash_password(new_password)
    user.must_change_password = True
    user.failed_login_attempts = 0
    user.locked_until = None
    sessions_repo.revoke_all_for_user(db, user.id)
    _record_audit(db, actor, "user.password_reset", user, {})
    db.commit()
    db.refresh(user)
    return user
