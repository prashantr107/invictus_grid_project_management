"""Shared pytest fixtures for the backend test suite."""

import pytest

from app.api.auth import limiter
from app.api.dependencies import get_db
from app.db.session import Base
from app.main import app
from app.models import ProjectMember, Role, Task, TaskStatus

from support import SessionLocal, TEST_DB, make_project, make_user, override_get_db

app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def database():
    Base.metadata.create_all(TEST_DB)
    yield
    Base.metadata.drop_all(TEST_DB)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """The login limiter keys on the client address, which is always
    `testclient` under Starlette's TestClient; reset it so one test's logins do
    not throttle the next."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def world():
    """A populated world: an ALPHA project (manager + member + peer member) and
    an unrelated OMEGA project, covering same-project, cross-member and
    cross-project authorization cases."""
    with SessionLocal() as db:
        admin = make_user(db, "Admin", "admin@invictusgrid.com", Role.ADMIN)
        manager = make_user(db, "Manager", "manager@invictusgrid.com", Role.MANAGER)
        member = make_user(db, "Member", "member@invictusgrid.com", Role.MEMBER)
        peer = make_user(db, "Peer Member", "peer@invictusgrid.com", Role.MEMBER)
        project = make_project(db, "ALPHA", manager.id, member.id)
        db.add(ProjectMember(project_id=project.id, user_id=peer.id, role=Role.MEMBER.value, added_by=manager.id))
        task = Task(
            project_id=project.id,
            issue_number=1,
            issue_key="ALPHA-1",
            title="First task",
            status=TaskStatus.TODO.value,
            created_by=manager.id,
            assignee_id=member.id,
        )

        other_manager = make_user(db, "Other Manager", "manager2@invictusgrid.com", Role.MANAGER)
        other_member = make_user(db, "Other Member", "member2@invictusgrid.com", Role.MEMBER)
        other_project = make_project(db, "OMEGA", other_manager.id, other_member.id)
        other_task = Task(
            project_id=other_project.id,
            issue_number=1,
            issue_key="OMEGA-1",
            title="Unrelated task",
            status=TaskStatus.TODO.value,
            created_by=other_manager.id,
            assignee_id=other_member.id,
        )

        db.add_all([task, other_task])
        db.commit()
        return {
            "admin_id": admin.id,
            "manager_id": manager.id,
            "member_id": member.id,
            "peer_member_id": peer.id,
            "other_manager_id": other_manager.id,
            "other_member_id": other_member.id,
            "project_id": project.id,
            "other_project_id": other_project.id,
            "task_id": task.id,
            "other_task_id": other_task.id,
        }
