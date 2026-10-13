"""Queries for the auth_sessions aggregate."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import AuthSession, utc_now


def add(db: Session, auth_session: AuthSession) -> AuthSession:
    db.add(auth_session)
    db.flush()
    return auth_session


def get(db: Session, session_id: UUID) -> AuthSession | None:
    return db.get(AuthSession, session_id)


def get_by_hash(db: Session, token_hash: str) -> AuthSession | None:
    return db.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == token_hash))


def get_by_hash_for_update(db: Session, token_hash: str) -> AuthSession | None:
    return db.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == token_hash).with_for_update())


def revoke_all_for_user(db: Session, user_id: UUID) -> None:
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )


def revoke_family(db: Session, family_id: UUID) -> None:
    db.execute(
        update(AuthSession)
        .where(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
