"""In-app notification endpoints and the triggers wired into task workflows
(SRS §3.10)."""

from fastapi.testclient import TestClient

from app.main import app

from support import auth_headers


def _client():
    return TestClient(app)


def _create_assigned_task(client, world, *, title="Notify task"):
    resp = client.post(
        f"/api/v1/projects/{world['project_id']}/tasks",
        headers=auth_headers(world["manager_id"]),
        json={"title": title, "assignee_id": str(world["member_id"])},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _types(client, user_id):
    page = client.get("/api/v1/notifications", headers=auth_headers(user_id))
    assert page.status_code == 200, page.text
    return [item["type"] for item in page.json()["items"]]


def test_assignment_notifies_assignee(world):
    client = _client()
    _create_assigned_task(client, world)
    assert "TASK_ASSIGNED" in _types(client, world["member_id"])


def test_submission_notifies_managers(world):
    client = _client()
    task = _create_assigned_task(client, world)
    client.patch(
        f"/api/v1/tasks/{task['id']}/status", headers=auth_headers(world["member_id"]), json={"status": "IN_PROGRESS"}
    )
    submitted = client.post(f"/api/v1/tasks/{task['id']}/submit-review", headers=auth_headers(world["member_id"]))
    assert submitted.status_code == 200, submitted.text
    assert "REVIEW_REQUESTED" in _types(client, world["manager_id"])


def test_approval_notifies_assignee(world):
    client = _client()
    task = _create_assigned_task(client, world)
    client.patch(
        f"/api/v1/tasks/{task['id']}/status", headers=auth_headers(world["member_id"]), json={"status": "IN_PROGRESS"}
    )
    client.post(f"/api/v1/tasks/{task['id']}/submit-review", headers=auth_headers(world["member_id"]))
    reviewed = client.post(
        f"/api/v1/tasks/{task['id']}/review",
        headers=auth_headers(world["manager_id"]),
        json={"decision": "APPROVED"},
    )
    assert reviewed.status_code == 201, reviewed.text
    assert "TASK_APPROVED" in _types(client, world["member_id"])


def test_changes_required_notifies_assignee(world):
    client = _client()
    task = _create_assigned_task(client, world)
    client.patch(
        f"/api/v1/tasks/{task['id']}/status", headers=auth_headers(world["member_id"]), json={"status": "IN_PROGRESS"}
    )
    client.post(f"/api/v1/tasks/{task['id']}/submit-review", headers=auth_headers(world["member_id"]))
    client.post(
        f"/api/v1/tasks/{task['id']}/review",
        headers=auth_headers(world["manager_id"]),
        json={"decision": "CHANGES_REQUIRED", "feedback": "Needs work"},
    )
    assert "CHANGES_REQUIRED" in _types(client, world["member_id"])


def test_mark_read_and_unread_filter(world):
    client = _client()
    _create_assigned_task(client, world)
    member_headers = auth_headers(world["member_id"])

    page = client.get("/api/v1/notifications", headers=member_headers)
    body = page.json()
    assert body["unread"] == 1
    notification_id = body["items"][0]["id"]

    marked = client.patch(f"/api/v1/notifications/{notification_id}/read", headers=member_headers)
    assert marked.status_code == 200, marked.text
    assert marked.json()["is_read"] is True

    unread_page = client.get("/api/v1/notifications?unread_only=true", headers=member_headers)
    assert unread_page.json()["items"] == []
    assert unread_page.json()["unread"] == 0


def test_cannot_mark_another_users_notification(world):
    client = _client()
    _create_assigned_task(client, world)
    notification_id = client.get("/api/v1/notifications", headers=auth_headers(world["member_id"])).json()["items"][0][
        "id"
    ]
    resp = client.patch(f"/api/v1/notifications/{notification_id}/read", headers=auth_headers(world["manager_id"]))
    assert resp.status_code == 404, resp.text
