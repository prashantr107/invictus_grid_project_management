"""Authentication workflows: credential verification, session issue/rotation/
revocation, access-token resolution, and password change.

`utc_now` is imported at module scope so the test harness can bind a
SQLite-compatible (naive) clock, mirroring `app.api.dependencies`.
"""

from datetime import timedelta
from uuid import UUID, uuid4

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


def _record_failed_login(db: Session, user: User) -> None:
    settings = get_settings()
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= settings.failed_login_max_attempts:
        user.failed_login_attempts = 0
        user.locked_until = utc_now() + timedelta(minutes=settings.failed_login_lockout_minutes)
        logger.warning("account_locked", extra={"event": "auth.account_locked"})
    db.commit()


def authenticate(db: Session, email: str, password: str) -> User:
    """Verify credentials, comparing against a dummy hash when the user is
    unknown so response timing does not reveal account existence.

    Repeated failures for an existing active account trip a timed lockout; the
    generic error is returned either way so lockout state is not enumerable."""
    user = users_repo.get_by_email(db, email)
    if user is not None and user.locked_until is not None and user.locked_until > utc_now():
        logger.info("login_locked", extra={"event": "auth.login_locked"})
        raise AuthenticationError("Invalid email or password")
    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_matches = verify_password(password, password_hash)
    if user is None or not user.is_active or not password_matches:
        if user is not None and user.is_active:
            _record_failed_login(db, user)
        logger.info("login_failed", extra={"event": "auth.login_failed"})
        raise AuthenticationError("Invalid email or password")
    if user.failed_login_attempts or user.locked_until is not None:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
    return user


def issue_session(db: Session, user: User, family_id: UUID | None = None) -> tuple[str, str]:
    settings = get_settings()
    refresh_token = new_refresh_token()
    auth_session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        expires_at=utc_now() + timedelta(days=settings.refresh_token_days),
        family_id=family_id or uuid4(),
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
    invalid, expired, or belongs to an inactive user.

    Replaying an already-rotated (revoked) token means the token was stolen or
    copied, so the entire rotation family is revoked."""
    old_session = sessions_repo.get_by_hash_for_update(db, hash_refresh_token(raw_token))
    if old_session is None:
        return None
    if old_session.revoked_at is not None:
        sessions_repo.revoke_family(db, old_session.family_id)
        db.commit()
        logger.warning("refresh_reuse_detected", extra={"event": "auth.refresh_reuse_detected"})
        return None
    user = users_repo.get(db, old_session.user_id)
    if old_session.expires_at <= utc_now() or user is None or not user.is_active:
        return None
    old_session.revoked_at = utc_now()
    new_token, access_token = issue_session(db, user, family_id=old_session.family_id)
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
