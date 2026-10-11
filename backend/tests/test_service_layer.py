"""Unit tests for the service layer, exercised without HTTP (TRD §3/§15:
services and business rules must be independently testable).
"""

import pytest

from app.core.errors import AuthenticationError, BadRequestError, ConflictError
from app.core.security import hash_password
from app.models import Role, TaskStatus, User
from app.repositories import users as users_repo
from app.schemas import TaskStatusUpdate, UserCreate
from app.services import auth as auth_service
from app.services import tasks as tasks_service
from app.services import users as users_service

from support import SessionLocal


def _user_with_password(db, email: str, password: str, role: Role = Role.MEMBER, active: bool = True) -> User:
    user = User(
        email=email,
        full_name="Real User",
        role=role.value,
        password_hash=hash_password(password),
        is_active=active,
        must_change_password=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_authenticate_rejects_unknown_email(world):
    with SessionLocal() as db:
        with pytest.raises(AuthenticationError):
            auth_service.authenticate(db, "nobody@invictusgrid.com", "GoodPassw0rd!1")


def test_authenticate_accepts_valid_credentials(world):
    with SessionLocal() as db:
        user = _user_with_password(db, "real@invictusgrid.com", "GoodPassw0rd!1")
        found = auth_service.authenticate(db, "real@invictusgrid.com", "GoodPassw0rd!1")
        assert found.id == user.id


def test_authenticate_rejects_inactive_user(world):
    with SessionLocal() as db:
        _user_with_password(db, "inactive@invictusgrid.com", "GoodPassw0rd!1", active=False)
        with pytest.raises(AuthenticationError):
            auth_service.authenticate(db, "inactive@invictusgrid.com", "GoodPassw0rd!1")


def test_resolve_access_token_rejects_garbage(world):
    with SessionLocal() as db:
        with pytest.raises(AuthenticationError):
            auth_service.resolve_access_token(db, "not-a-real-jwt")


def test_change_password_rejects_wrong_current(world):
    with SessionLocal() as db:
        user = _user_with_password(db, "cp1@invictusgrid.com", "GoodPassw0rd!1")
        with pytest.raises(BadRequestError):
            auth_service.change_password(db, user, "WrongPassw0rd!1", "NewPassw0rd!22")


def test_change_password_rejects_reusing_current(world):
    with SessionLocal() as db:
        user = _user_with_password(db, "cp2@invictusgrid.com", "GoodPassw0rd!1")
        with pytest.raises(BadRequestError):
            auth_service.change_password(db, user, "GoodPassw0rd!1", "GoodPassw0rd!1")


def test_create_user_duplicate_email_conflicts(world):
    with SessionLocal() as db:
        admin = users_repo.get(db, world["admin_id"])
        payload = UserCreate(
            email="dup@invictusgrid.com", full_name="Dup", role=Role.MEMBER, initial_password="GoodPassw0rd!1"
        )
        users_service.create_user(db, admin, payload)
        with pytest.raises(ConflictError):
            users_service.create_user(db, admin, payload)


def test_set_active_blocks_self_deactivation(world):
    with SessionLocal() as db:
        admin = users_repo.get(db, world["admin_id"])
        with pytest.raises(BadRequestError):
            users_service.set_active(db, admin, admin.id, False)


def test_start_task_rejects_invalid_transition(world):
    with SessionLocal() as db:
        member = users_repo.get(db, world["member_id"])
        payload = TaskStatusUpdate(status=TaskStatus.IN_PROGRESS)
        tasks_service.start_task(db, member, world["task_id"], payload)
        with pytest.raises(ConflictError):
            tasks_service.start_task(db, member, world["task_id"], payload)
