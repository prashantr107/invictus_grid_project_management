"""C5 regression tests: role changes must not break project access.

Covers the "decouple + reconcile" decision:
- `project_members.role` is the source of truth for project-level authorization.
- Promotion MEMBER -> MANAGER preserves existing memberships (no access loss, no
  automatic manager authority).
- Demotion MANAGER -> MEMBER downgrades MANAGER memberships to MEMBER (no
  privilege escalation) and is audited.

Run from backend/:  python -m pytest tests/test_c5_authorization.py -v
"""

from datetime import datetime, timedelta, timezone
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.dependencies as dependencies_module
import app.models as models_module
from app.api.dependencies import get_db
from app.core.security import create_access_token, hash_refresh_token
from app.db.session import Base
from app.main import app
from app.models import AuthSession, Project, ProjectMember, Role, Task, TaskStatus, User, utc_now

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
dependencies_module.utc_now = _naive_utc_now
models_module.utc_now = _naive_utc_now


def override_get_db():
    with SessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def database():
    Base.metadata.create_all(TEST_DB)
    yield
    Base.metadata.drop_all(TEST_DB)


def make_user(db, name, email, role):
    user = User(
        email=email,
        full_name=name,
        role=role.value,
        password_hash="not-a-real-hash",
        is_active=True,
        must_change_password=False,
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


def make_project(db, key, manager_id, member_id):
    project = Project(key=key, name=key, status="ACTIVE", created_by=manager_id)
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=manager_id, role=Role.MANAGER.value, added_by=manager_id))
    db.add(ProjectMember(project_id=project.id, user_id=member_id, role=Role.MEMBER.value, added_by=manager_id))
    return project


@pytest.fixture
def world():
    with SessionLocal() as db:
        admin = make_user(db, "Admin", "admin@invictusgrid.com", Role.ADMIN)
        manager = make_user(db, "Manager", "manager@invictusgrid.com", Role.MANAGER)
        member = make_user(db, "Member", "member@invictusgrid.com", Role.MEMBER)
        project = make_project(db, "ALPHA", manager.id, member.id)
        task = Task(
            project_id=project.id,
            issue_number=1,
            issue_key="ALPHA-1",
            title="First task",
            status=TaskStatus.TODO.value,
            created_by=manager.id,
            assignee_id=member.id,
        )
        db.add(task)
        db.commit()
        return {
            "admin_id": admin.id,
            "manager_id": manager.id,
            "member_id": member.id,
            "project_id": project.id,
            "task_id": task.id,
        }


def auth_headers(user_id):
    return {"Authorization": f"Bearer {make_token(user_id)}"}


def test_promotion_preserves_member_access_to_own_tasks(world):
    member_id = world["member_id"]
    admin_id = world["admin_id"]
    project_id = world["project_id"]
    task_id = world["task_id"]

    client = TestClient(app)
    change = client.patch(f"/api/v1/users/{member_id}/role", headers=auth_headers(admin_id), json={"role": "MANAGER"})
    assert change.status_code == 200, change.text

    headers = auth_headers(member_id)

    tasks = client.get(f"/api/v1/projects/{project_id}/tasks", headers=headers)
    assert tasks.status_code == 200, tasks.text
    assert [t["id"] for t in tasks.json()["items"]] == [str(task_id)]

    started = client.patch(f"/api/v1/tasks/{task_id}/status", headers=headers, json={"status": "IN_PROGRESS"})
    assert started.status_code == 200, started.text
    submitted = client.post(f"/api/v1/tasks/{task_id}/submit-review", headers=headers)
    assert submitted.status_code == 200, submitted.text


def test_promotion_does_not_grant_manager_authority(world):
    member_id = world["member_id"]
    admin_id = world["admin_id"]
    project_id = world["project_id"]

    client = TestClient(app)
    change = client.patch(f"/api/v1/users/{member_id}/role", headers=auth_headers(admin_id), json={"role": "MANAGER"})
    assert change.status_code == 200, change.text

    headers = auth_headers(member_id)

    build = client.post(f"/api/v1/projects/{project_id}/tasks", headers=headers, json={"title": "Should fail"})
    assert build.status_code == 404, build.text
    members = client.get(f"/api/v1/projects/{project_id}/members", headers=headers)
    assert members.status_code == 403, members.text


def test_demotion_reconciles_memberships_and_blocks_escalation(world):
    manager_id = world["manager_id"]
    admin_id = world["admin_id"]
    project_id = world["project_id"]
    task_id = world["task_id"]

    client = TestClient(app)
    change = client.patch(f"/api/v1/users/{manager_id}/role", headers=auth_headers(admin_id), json={"role": "MEMBER"})
    assert change.status_code == 200, change.text

    with SessionLocal() as db:
        membership = db.get(ProjectMember, (project_id, manager_id))
        assert membership is not None
        assert membership.role == Role.MEMBER.value

    headers = auth_headers(manager_id)
    build = client.post(f"/api/v1/projects/{project_id}/tasks", headers=headers, json={"title": "Should fail"})
    assert build.status_code == 404, build.text
    members = client.get(f"/api/v1/projects/{project_id}/members", headers=headers)
    assert members.status_code == 403, members.text
    review = client.post(f"/api/v1/tasks/{task_id}/review", headers=headers, json={"decision": "APPROVED"})
    assert review.status_code == 404, review.text


def test_manager_account_keeps_manager_authority(world):
    manager_id = world["manager_id"]
    project_id = world["project_id"]

    client = TestClient(app)
    headers = auth_headers(manager_id)

    build = client.post(
        f"/api/v1/projects/{project_id}/tasks",
        headers=headers,
        json={"title": "Managed work", "assignee_id": str(world["member_id"])},
    )
    assert build.status_code == 201, build.text
    members = client.get(f"/api/v1/projects/{project_id}/members", headers=headers)
    assert members.status_code == 200, members.text


def test_demotion_is_audit_logged(world):
    from app.models import AuditLog

    manager_id = world["manager_id"]
    admin_id = world["admin_id"]

    client = TestClient(app)
    headers = auth_headers(admin_id)
    resp = client.patch(f"/api/v1/users/{manager_id}/role", headers=headers, json={"role": "MEMBER"})
    assert resp.status_code == 200, resp.text

    with SessionLocal() as db:
        log = db.query(AuditLog).filter_by(action="user.role_changed").order_by(AuditLog.created_at.desc()).first()
        assert log is not None
        assert log.details["new"] == "MEMBER"
        assert log.details["previous"] == "MANAGER"
        assert len(log.details["memberships_downgraded_to_member"]) == 1
