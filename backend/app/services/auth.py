"""Authentication workflows: credential verification, session issue/rotation/
revocation, access-token resolution, and password change.

`utc_now` is imported at module scope so the test harness can bind a
SQLite-compatible (naive) clock, mirroring `app.api.dependencies`.
"""

from datetime import timedelta
from uuid import UUID

import jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AuthenticationError, BadRequestError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.models import AuthSession, User, utc_now
from app.repositories import sessions as sessions_repo
from app.repositories import users as users_repo

logger = get_logger("app.auth")

_DUMMY_PASSWORD_HASH = hash_password("TimingOnly-NotARealAccount-93!")


def authenticate(db: Session, email: str, password: str) -> User:
    """Verify credentials, comparing against a dummy hash when the user is
    unknown so response timing does not reveal account existence."""
    user = users_repo.get_by_email(db, email)
    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_matches = verify_password(password, password_hash)
    if user is None or not user.is_active or not password_matches:
        logger.info("login_failed", extra={"event": "auth.login_failed"})
        raise AuthenticationError("Invalid email or password")
    return user


def issue_session(db: Session, user: User) -> tuple[str, str]:
    settings = get_settings()
    refresh_token = new_refresh_token()
    auth_session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        expires_at=utc_now() + timedelta(days=settings.refresh_token_days),
    )
    sessions_repo.add(db, auth_session)
    return refresh_token, create_access_token(user.id, auth_session.id)


def login(db: Session, email: str, password: str) -> tuple[User, str, str]:
    user = authenticate(db, email, password)
    refresh_token, access_token = issue_session(db, user)
    db.commit()
    return user, refresh_token, access_token


def rotate(db: Session, raw_token: str) -> tuple[User, str, str] | None:
    """Rotate a refresh token. Returns None when the presented token is
    invalid, revoked, expired, or belongs to an inactive user."""
    old_session = sessions_repo.get_by_hash_for_update(db, hash_refresh_token(raw_token))
    user = users_repo.get(db, old_session.user_id) if old_session else None
    if (
        old_session is None
        or old_session.revoked_at is not None
        or old_session.expires_at <= utc_now()
        or user is None
        or not user.is_active
    ):
        return None
    old_session.revoked_at = utc_now()
    new_token, access_token = issue_session(db, user)
    db.commit()
    return user, new_token, access_token


def revoke(db: Session, raw_token: str) -> None:
    auth_session = sessions_repo.get_by_hash(db, hash_refresh_token(raw_token))
    if auth_session and auth_session.revoked_at is None:
        auth_session.revoked_at = utc_now()
        db.commit()


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise BadRequestError("Current password is incorrect")
    if verify_password(new_password, user.password_hash):
        raise BadRequestError("Choose a different password")
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    sessions_repo.revoke_all_for_user(db, user.id)
    db.commit()
    logger.info("password_changed", extra={"event": "auth.password_changed"})


def resolve_access_token(db: Session, token: str) -> User:
    """Resolve a bearer access token to its still-valid, active user."""
    unauthorized = AuthenticationError()
    try:
        claims = decode_access_token(token)
        if claims.get("type") != "access":
            raise unauthorized
        user_id = UUID(claims["sub"])
        session_id = UUID(claims["sid"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise unauthorized from None

    auth_session = sessions_repo.get(db, session_id)
    user = users_repo.get(db, user_id)
    if (
        auth_session is None
        or auth_session.user_id != user_id
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= utc_now()
        or user is None
        or not user.is_active
    ):
        raise unauthorized
    return user
