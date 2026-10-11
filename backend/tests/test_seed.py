"""Tests for the local demo seed script (`app.seed`)."""

import pytest
from sqlalchemy import func, select

from app.models import Project, Task, TaskStatus, User
from app.seed import seed

from support import SessionLocal


def test_seed_populates_demo_data():
    with SessionLocal() as db:
        summary = seed(db)

    assert summary["project_key"] == "ALPHA"
    assert summary["tasks"] == 5
    assert summary["progress"] == 40

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 4
        assert db.scalar(select(func.count()).select_from(Project)) == 1
        assert db.scalar(select(func.count()).select_from(Task)) == 5
        completed = db.scalar(select(func.count()).select_from(Task).where(Task.status == TaskStatus.COMPLETED.value))
        assert completed == 2


def test_seed_refuses_when_accounts_exist(world):
    with SessionLocal() as db:
        with pytest.raises(RuntimeError):
            seed(db)
