"""Shared pytest fixtures for the backend test suite."""

import pytest

from app.api.dependencies import get_db
from app.db.session import Base
from app.main import app
from app.models import Role, Task, TaskStatus

from support import SessionLocal, TEST_DB, make_project, make_user, override_get_db

app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def database():
    Base.metadata.create_all(TEST_DB)
    yield
    Base.metadata.drop_all(TEST_DB)


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
