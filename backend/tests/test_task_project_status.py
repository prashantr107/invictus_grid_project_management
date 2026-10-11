"""Regression tests for the shared COMPLETED/ARCHIVED project guard.

`create_task` already refused to add work to a completed/archived project; the
same guard now covers `update_task` and `review_task`, and the now-unreachable
role check in `create_task` was removed without changing the 404 contract for
non-managers.
"""

from fastapi.testclient import TestClient

from app.main import app

from support import auth_headers, set_project_status


def test_update_task_blocked_in_completed_project(world):
    set_project_status(world["project_id"], "COMPLETED")
    client = TestClient(app)
    resp = client.patch(
        f"/api/v1/tasks/{world['task_id']}", headers=auth_headers(world["manager_id"]), json={"title": "Nope"}
    )
    assert resp.status_code == 409, resp.text


def test_update_task_blocked_in_archived_project(world):
    set_project_status(world["project_id"], "ARCHIVED")
    client = TestClient(app)
    resp = client.patch(
        f"/api/v1/tasks/{world['task_id']}", headers=auth_headers(world["manager_id"]), json={"title": "Nope"}
    )
    assert resp.status_code == 409, resp.text


def test_review_blocked_in_archived_project(world):
    set_project_status(world["project_id"], "ARCHIVED")
    client = TestClient(app)
    resp = client.post(
        f"/api/v1/tasks/{world['task_id']}/review",
        headers=auth_headers(world["manager_id"]),
        json={"decision": "APPROVED"},
    )
    assert resp.status_code == 409, resp.text


def test_create_blocked_in_archived_project(world):
    set_project_status(world["project_id"], "ARCHIVED")
    client = TestClient(app)
    resp = client.post(
        f"/api/v1/projects/{world['project_id']}/tasks",
        headers=auth_headers(world["manager_id"]),
        json={"title": "Nope"},
    )
    assert resp.status_code == 409, resp.text


def test_update_task_allowed_in_active_project(world):
    client = TestClient(app)
    resp = client.patch(
        f"/api/v1/tasks/{world['task_id']}", headers=auth_headers(world["manager_id"]), json={"title": "Still fine"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "Still fine"


def test_plain_member_cannot_create_task(world):
    client = TestClient(app)
    resp = client.post(
        f"/api/v1/projects/{world['project_id']}/tasks",
        headers=auth_headers(world["member_id"]),
        json={"title": "Nope"},
    )
    assert resp.status_code == 404, resp.text
