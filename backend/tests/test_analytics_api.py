"""Project analytics/dashboard endpoint (SRS §3.11)."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.models import Task, TaskPriority, TaskStatus

from support import SessionLocal, auth_headers


def _client():
    return TestClient(app)


def _seed_metrics(world):
    yesterday = date.today() - timedelta(days=1)
    with SessionLocal() as db:
        db.add(
            Task(
                project_id=world["project_id"],
                issue_number=2,
                issue_key="ALPHA-2",
                title="Done task",
                status=TaskStatus.COMPLETED.value,
                priority=TaskPriority.HIGH.value,
                created_by=world["manager_id"],
                assignee_id=world["member_id"],
                due_date=yesterday,
            )
        )
        db.add(
            Task(
                project_id=world["project_id"],
                issue_number=3,
                issue_key="ALPHA-3",
                title="Overdue task",
                status=TaskStatus.IN_PROGRESS.value,
                priority=TaskPriority.LOW.value,
                created_by=world["manager_id"],
                assignee_id=world["peer_member_id"],
                due_date=yesterday,
            )
        )
        db.commit()


def test_project_analytics_aggregates(world):
    _seed_metrics(world)
    resp = _client().get(f"/api/v1/projects/{world['project_id']}/analytics", headers=auth_headers(world["manager_id"]))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_tasks"] == 3
    assert body["by_status"]["COMPLETED"] == 1
    assert body["by_status"]["IN_PROGRESS"] == 1
    assert body["by_priority"]["HIGH"] == 1
    assert body["progress"] == 33
    assert body["overdue"] == 1

    contributions = {c["user_id"]: c for c in body["contributions"]}
    member = contributions[str(world["member_id"])]
    assert member["assigned"] == 2
    assert member["completed"] == 1
    peer = contributions[str(world["peer_member_id"])]
    assert peer["assigned"] == 1
    assert peer["overdue"] == 1


def test_project_analytics_visibility(world):
    resp = _client().get(
        f"/api/v1/projects/{world['project_id']}/analytics", headers=auth_headers(world["other_manager_id"])
    )
    assert resp.status_code == 404, resp.text


def test_project_analytics_empty_progress(world):
    resp = _client().get(
        f"/api/v1/projects/{world['other_project_id']}/analytics", headers=auth_headers(world["other_manager_id"])
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["progress"] == 0
