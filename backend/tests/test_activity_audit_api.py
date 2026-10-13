"""Activity feed and Admin audit-log endpoints (SRS §3.12)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

from support import auth_headers


def _client():
    return TestClient(app)


# --- activity ---------------------------------------------------------------


@pytest.mark.parametrize(
    "actor,expected",
    [("admin", 200), ("manager", 200), ("member", 200), ("peer_member", 200), ("other_manager", 404), ("anon", 401)],
)
def test_project_activity_visibility(world, actor, expected):
    headers = {} if actor == "anon" else auth_headers(world[f"{actor}_id"])
    resp = _client().get(f"/api/v1/projects/{world['project_id']}/activity", headers=headers)
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize(
    "actor,expected",
    [("admin", 200), ("manager", 200), ("member", 200), ("peer_member", 404), ("other_member", 404), ("anon", 401)],
)
def test_task_activity_visibility(world, actor, expected):
    headers = {} if actor == "anon" else auth_headers(world[f"{actor}_id"])
    resp = _client().get(f"/api/v1/tasks/{world['task_id']}/activity", headers=headers)
    assert resp.status_code == expected, resp.text


def test_activity_records_task_actions(world):
    client = _client()
    created = client.post(
        f"/api/v1/projects/{world['project_id']}/tasks",
        headers=auth_headers(world["manager_id"]),
        json={"title": "Tracked", "assignee_id": str(world["member_id"])},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    page = client.get(f"/api/v1/tasks/{task_id}/activity", headers=auth_headers(world["manager_id"]))
    actions = [entry["action"] for entry in page.json()["items"]]
    assert "task.created" in actions
    assert "task.assigned" in actions


# --- audit ------------------------------------------------------------------


@pytest.mark.parametrize("actor,expected", [("admin", 200), ("manager", 403), ("member", 403), ("anon", 401)])
def test_audit_log_requires_admin(world, actor, expected):
    headers = {} if actor == "anon" else auth_headers(world[f"{actor}_id"])
    resp = _client().get("/api/v1/audit-logs", headers=headers)
    assert resp.status_code == expected, resp.text


def test_audit_log_lists_privileged_actions(world):
    client = _client()
    created = client.post(
        f"/api/v1/projects/{world['project_id']}/tasks",
        headers=auth_headers(world["manager_id"]),
        json={"title": "Audited"},
    )
    assert created.status_code == 201, created.text

    page = client.get("/api/v1/audit-logs", headers=auth_headers(world["admin_id"]))
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["total"] >= 1
    assert any(entry["action"] == "task.created" for entry in body["items"])
