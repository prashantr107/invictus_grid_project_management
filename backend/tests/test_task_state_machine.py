"""Service-level task state-machine tests (TRD §15): every allowed transition
passes and every disallowed transition / unauthorized actor fails.

These call the service layer directly (no HTTP), so they pin the workflow rules
independently of routing.
"""

import pytest

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models import Task, TaskStatus
from app.repositories import users as users_repo
from app.schemas import TaskReviewCreate, TaskStatusUpdate, TaskUpdate
from app.services import tasks as tasks_service

from support import SessionLocal

START = TaskStatusUpdate(status=TaskStatus.IN_PROGRESS)


def _status(db, task_id) -> str:
    return db.get(Task, task_id).status


def test_happy_path_reaches_completed(world):
    with SessionLocal() as db:
        member = users_repo.get(db, world["member_id"])
        manager = users_repo.get(db, world["manager_id"])
        task_id = world["task_id"]

        assert tasks_service.start_task(db, member, task_id, START).status == TaskStatus.IN_PROGRESS
        assert tasks_service.submit_for_review(db, member, task_id).status == TaskStatus.PENDING_REVIEW
        review = tasks_service.review_task(db, manager, task_id, TaskReviewCreate(decision="APPROVED"))

        assert review.decision == "APPROVED"
        task = db.get(Task, task_id)
        assert task.status == TaskStatus.COMPLETED.value
        assert task.completed_at is not None


def test_submit_requires_in_progress(world):
    with SessionLocal() as db:
        member = users_repo.get(db, world["member_id"])
        with pytest.raises(ConflictError):
            tasks_service.submit_for_review(db, member, world["task_id"])


def test_review_requires_pending_review(world):
    with SessionLocal() as db:
        manager = users_repo.get(db, world["manager_id"])
        with pytest.raises(ConflictError):
            tasks_service.review_task(db, manager, world["task_id"], TaskReviewCreate(decision="APPROVED"))


def test_cannot_start_twice(world):
    with SessionLocal() as db:
        member = users_repo.get(db, world["member_id"])
        tasks_service.start_task(db, member, world["task_id"], START)
        with pytest.raises(ConflictError):
            tasks_service.start_task(db, member, world["task_id"], START)


def test_cannot_start_from_pending_review(world):
    with SessionLocal() as db:
        member = users_repo.get(db, world["member_id"])
        tasks_service.start_task(db, member, world["task_id"], START)
        tasks_service.submit_for_review(db, member, world["task_id"])
        with pytest.raises(ConflictError):
            tasks_service.start_task(db, member, world["task_id"], START)


def test_changes_required_can_resume_and_complete(world):
    with SessionLocal() as db:
        member = users_repo.get(db, world["member_id"])
        manager = users_repo.get(db, world["manager_id"])
        task_id = world["task_id"]

        tasks_service.start_task(db, member, task_id, START)
        tasks_service.submit_for_review(db, member, task_id)
        tasks_service.review_task(db, manager, task_id, TaskReviewCreate(decision="CHANGES_REQUIRED", feedback="Redo"))
        assert _status(db, task_id) == TaskStatus.CHANGES_REQUIRED.value

        assert tasks_service.start_task(db, member, task_id, START).status == TaskStatus.IN_PROGRESS
        tasks_service.submit_for_review(db, member, task_id)
        tasks_service.review_task(db, manager, task_id, TaskReviewCreate(decision="APPROVED"))
        assert _status(db, task_id) == TaskStatus.COMPLETED.value


def test_manager_cannot_start_or_submit(world):
    with SessionLocal() as db:
        member = users_repo.get(db, world["member_id"])
        manager = users_repo.get(db, world["manager_id"])
        task_id = world["task_id"]

        with pytest.raises(ForbiddenError):
            tasks_service.start_task(db, manager, task_id, START)

        tasks_service.start_task(db, member, task_id, START)
        with pytest.raises(ForbiddenError):
            tasks_service.submit_for_review(db, manager, task_id)


def test_non_assignee_member_cannot_start(world):
    with SessionLocal() as db:
        peer = users_repo.get(db, world["peer_member_id"])
        with pytest.raises(NotFoundError):
            tasks_service.start_task(db, peer, world["task_id"], START)


def test_update_requires_at_least_one_field(world):
    with SessionLocal() as db:
        manager = users_repo.get(db, world["manager_id"])
        with pytest.raises(ValidationError):
            tasks_service.update_task(db, manager, world["task_id"], TaskUpdate())


def test_reassignment_updates_assignee(world):
    with SessionLocal() as db:
        manager = users_repo.get(db, world["manager_id"])
        updated = tasks_service.update_task(
            db, manager, world["task_id"], TaskUpdate(assignee_id=world["peer_member_id"])
        )
        assert updated.assignee_id == world["peer_member_id"]
