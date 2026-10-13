"""Shared test harness: an in-memory SQLite session plus fixture builders.

No Postgres/Docker is required — every test runs against this engine with the
`get_db` dependency overridden in `conftest.py`.
"""

from datetime import datetime, timedelta, timezone
import secrets

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models as models_module
import app.services.auth as auth_service_module
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.models import AuthSession, Project, ProjectMember, Role, User, utc_now

TEST_DB = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(bind=TEST_DB, autoflush=False, autocommit=False, expire_on_commit=False)


def _naive_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# SQLite has no timezone support: keep timestamps naive so auth-session expiry
# comparisons (aware utc_now vs naive column) do not raise.
models_module.utc_now = _naive_utc_now
auth_service_module.utc_now = _naive_utc_now


def override_get_db():
    with SessionLocal() as session:
        yield session


def make_user(db, name, email, role, *, password=None, must_change_password=False):
    user = User(
        email=email,
        full_name=name,
        role=role.value,
        password_hash=hash_password(password) if password else "not-a-real-hash",
        is_active=True,
        must_change_password=must_change_password,
    )
    db.add(user)
    db.flush()
    return user


def make_token(user_id):
    with SessionLocal() as db:
        session = AuthSession(
            user_id=user_id,
            refresh_token_hash=hash_refresh_token(secrets.token_urlsafe(24)),
            expires_at=utc_now() + timedelta(hours=1),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return create_access_token(session.user_id, session.id)


def make_project(db, key, manager_id, member_id, status="ACTIVE"):
    project = Project(key=key, name=key, status=status, created_by=manager_id)
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=manager_id, role=Role.MANAGER.value, added_by=manager_id))
    db.add(ProjectMember(project_id=project.id, user_id=member_id, role=Role.MEMBER.value, added_by=manager_id))
    return project


def auth_headers(user_id):
    return {"Authorization": f"Bearer {make_token(user_id)}"}


def set_project_status(project_id, status):
    with SessionLocal() as db:
        db.get(Project, project_id).status = status
        db.commit()
