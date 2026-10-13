"""Task deletion and list sorting (Phase 6)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

from support import auth_headers


def _client():
    return TestClient(app)


@pytest.mark.parametrize("actor,expected", [("admin", 204), ("manager", 204), ("member", 404), ("anon", 401)])
def test_delete_task_authorization(world, actor, expected):
    headers = {} if actor == "anon" else auth_headers(world[f"{actor}_id"])
    resp = _client().delete(f"/api/v1/tasks/{world['task_id']}", headers=headers)
    assert resp.status_code == expected, resp.text


def test_deleted_task_is_gone(world):
    client = _client()
    deleted = client.delete(f"/api/v1/tasks/{world['task_id']}", headers=auth_headers(world["manager_id"]))
    assert deleted.status_code == 204, deleted.text
    assert client.get(f"/api/v1/tasks/{world['task_id']}", headers=auth_headers(world["manager_id"])).status_code == 404


def test_task_list_sort_by_priority(world):
    client = _client()
    for priority in ("LOW", "HIGH", "URGENT"):
        resp = client.post(
            f"/api/v1/projects/{world['project_id']}/tasks",
            headers=auth_headers(world["manager_id"]),
            json={"title": f"{priority} task", "priority": priority},
        )
        assert resp.status_code == 201, resp.text

    page = client.get(
        f"/api/v1/projects/{world['project_id']}/tasks?sort=priority_desc",
        headers=auth_headers(world["manager_id"]),
    )
    assert page.status_code == 200, page.text
    priorities = [item["priority"] for item in page.json()["items"]]
    assert priorities == ["URGENT", "HIGH", "MEDIUM", "LOW"]


def test_task_list_rejects_invalid_sort(world):
    resp = _client().get(
        f"/api/v1/projects/{world['project_id']}/tasks?sort=sideways", headers=auth_headers(world["manager_id"])
    )
    assert resp.status_code == 422, resp.text
