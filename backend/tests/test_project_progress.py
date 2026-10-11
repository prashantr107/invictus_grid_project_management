"""Tests for server-side project progress (SRS §3.11):
completed tasks / total tasks × 100, 0 when the project has no tasks.
"""

from fastapi.testclient import TestClient

from app.main import app

from support import auth_headers


def _project(client, actor_id, project_id):
    resp = client.get("/api/v1/projects", headers=auth_headers(actor_id))
    assert resp.status_code == 200, resp.text
    return next(p for p in resp.json()["items"] if p["id"] == str(project_id))


def test_progress_is_zero_without_completed_tasks(world):
    client = TestClient(app)
    assert _project(client, world["admin_id"], world["project_id"])["progress"] == 0


def test_progress_reflects_completed_ratio(world):
    client = TestClient(app)
    member = auth_headers(world["member_id"])
    manager = auth_headers(world["manager_id"])

    started = client.patch(f"/api/v1/tasks/{world['task_id']}/status", headers=member, json={"status": "IN_PROGRESS"})
    assert started.status_code == 200, started.text
    submitted = client.post(f"/api/v1/tasks/{world['task_id']}/submit-review", headers=member)
    assert submitted.status_code == 200, submitted.text
    reviewed = client.post(f"/api/v1/tasks/{world['task_id']}/review", headers=manager, json={"decision": "APPROVED"})
    assert reviewed.status_code == 201, reviewed.text

    assert _project(client, world["manager_id"], world["project_id"])["progress"] == 100


def test_progress_is_zero_for_empty_project(world):
    client = TestClient(app)
    created = client.post(
        "/api/v1/projects",
        headers=auth_headers(world["admin_id"]),
        json={
            "key": "BETA",
            "name": "Beta Project",
            "manager_ids": [str(world["manager_id"])],
            "member_ids": [str(world["member_id"])],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["progress"] == 0
