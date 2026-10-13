"""Authorization matrix (Phase 11 / TRD §15, SRS §8.2): every endpoint is
exercised for each actor role (Admin / Manager / Member / peer Member /
unrelated Manager / anonymous), plus IDOR/BOLA cross-project and cross-member
cases.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Task, TaskStatus

from support import SessionLocal, auth_headers

ACTOR_KEYS = {
    "admin": "admin_id",
    "manager": "manager_id",
    "member": "member_id",
    "peer_member": "peer_member_id",
    "other_manager": "other_manager_id",
    "other_member": "other_member_id",
}


def _auth(world, actor):
    if actor == "anon":
        return {}
    return auth_headers(world[ACTOR_KEYS[actor]])


def _client():
    return TestClient(app)


# --- Admin-only user management -------------------------------------------------


@pytest.mark.parametrize("actor,expected", [("admin", 201), ("manager", 403), ("member", 403), ("anon", 401)])
def test_create_user(world, actor, expected):
    resp = _client().post(
        "/api/v1/users",
        headers=_auth(world, actor),
        json={
            "email": "fresh@invictusgrid.com",
            "full_name": "Fresh User",
            "role": "MEMBER",
            "initial_password": "GoodPassw0rd!1",
        },
    )
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize("actor,expected", [("admin", 200), ("manager", 403), ("member", 403), ("anon", 401)])
def test_list_users(world, actor, expected):
    resp = _client().get("/api/v1/users", headers=_auth(world, actor))
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize("actor,expected", [("admin", 200), ("manager", 403), ("member", 403), ("anon", 401)])
def test_update_user_status(world, actor, expected):
    resp = _client().patch(
        f"/api/v1/users/{world['member_id']}/status", headers=_auth(world, actor), json={"is_active": True}
    )
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize("actor,expected", [("admin", 200), ("manager", 403), ("member", 403), ("anon", 401)])
def test_update_user_role(world, actor, expected):
    resp = _client().patch(
        f"/api/v1/users/{world['member_id']}/role", headers=_auth(world, actor), json={"role": "MEMBER"}
    )
    assert resp.status_code == expected, resp.text


# --- Projects -------------------------------------------------------------------


@pytest.mark.parametrize("actor,expected", [("admin", 201), ("manager", 403), ("member", 403), ("anon", 401)])
def test_create_project(world, actor, expected):
    resp = _client().post(
        "/api/v1/projects",
        headers=_auth(world, actor),
        json={
            "key": "GAMMA",
            "name": "Gamma",
            "manager_ids": [str(world["manager_id"])],
            "member_ids": [str(world["member_id"])],
        },
    )
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize(
    "actor,expected",
    [("admin", 200), ("manager", 200), ("member", 200), ("anon", 401)],
)
def test_list_projects(world, actor, expected):
    resp = _client().get("/api/v1/projects", headers=_auth(world, actor))
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize(
    "actor,expected",
    [
        ("admin", 200),
        ("manager", 200),
        ("member", 403),
        ("peer_member", 403),
        ("other_manager", 404),
        ("anon", 401),
    ],
)
def test_get_project_members(world, actor, expected):
    resp = _client().get(f"/api/v1/projects/{world['project_id']}/members", headers=_auth(world, actor))
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize("actor,expected", [("admin", 200), ("manager", 403), ("member", 403), ("anon", 401)])
def test_replace_project_members(world, actor, expected):
    resp = _client().put(
        f"/api/v1/projects/{world['project_id']}/members",
        headers=_auth(world, actor),
        json={"manager_ids": [str(world["manager_id"])], "member_ids": [str(world["member_id"])]},
    )
    assert resp.status_code == expected, resp.text


# --- Tasks ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "actor,expected",
    [
        ("admin", 201),
        ("manager", 201),
        ("member", 404),
        ("peer_member", 404),
        ("other_manager", 404),
        ("anon", 401),
    ],
)
def test_create_task(world, actor, expected):
    resp = _client().post(
        f"/api/v1/projects/{world['project_id']}/tasks", headers=_auth(world, actor), json={"title": "New task"}
    )
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize(
    "actor,expected",
    [
        ("admin", 200),
        ("manager", 200),
        ("member", 200),
        ("peer_member", 200),
        ("other_manager", 404),
        ("anon", 401),
    ],
)
def test_list_project_tasks(world, actor, expected):
    resp = _client().get(f"/api/v1/projects/{world['project_id']}/tasks", headers=_auth(world, actor))
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize(
    "actor,expected",
    [
        ("admin", 200),
        ("manager", 200),
        ("member", 200),
        ("peer_member", 404),
        ("other_member", 404),
        ("anon", 401),
    ],
)
def test_get_task(world, actor, expected):
    resp = _client().get(f"/api/v1/tasks/{world['task_id']}", headers=_auth(world, actor))
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize(
    "actor,expected",
    [("admin", 200), ("manager", 200), ("member", 200), ("peer_member", 404), ("anon", 401)],
)
def test_list_task_reviews(world, actor, expected):
    resp = _client().get(f"/api/v1/tasks/{world['task_id']}/reviews", headers=_auth(world, actor))
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize(
    "actor,expected",
    [
        ("admin", 200),
        ("manager", 200),
        ("member", 404),
        ("peer_member", 404),
        ("other_manager", 404),
        ("anon", 401),
    ],
)
def test_update_task(world, actor, expected):
    resp = _client().patch(f"/api/v1/tasks/{world['task_id']}", headers=_auth(world, actor), json={"title": "Updated"})
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize(
    "actor,expected",
    [("member", 200), ("manager", 403), ("admin", 403), ("peer_member", 404), ("anon", 401)],
)
def test_start_task(world, actor, expected):
    resp = _client().patch(
        f"/api/v1/tasks/{world['task_id']}/status", headers=_auth(world, actor), json={"status": "IN_PROGRESS"}
    )
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize(
    "actor,expected",
    [("member", 409), ("manager", 403), ("admin", 403), ("peer_member", 404), ("anon", 401)],
)
def test_submit_review_guards(world, actor, expected):
    # The task is still TODO, so even the assignee gets a 409 (wrong state).
    resp = _client().post(f"/api/v1/tasks/{world['task_id']}/submit-review", headers=_auth(world, actor))
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize(
    "actor,expected",
    [("manager", 409), ("admin", 409), ("member", 404), ("peer_member", 404), ("anon", 401)],
)
def test_review_task_guards(world, actor, expected):
    # The task is not PENDING_REVIEW, so managers get a 409 (wrong state).
    resp = _client().post(
        f"/api/v1/tasks/{world['task_id']}/review", headers=_auth(world, actor), json={"decision": "APPROVED"}
    )
    assert resp.status_code == expected, resp.text


# --- Auth / health --------------------------------------------------------------


@pytest.mark.parametrize("actor,expected", [("admin", 200), ("member", 200), ("anon", 401)])
def test_me(world, actor, expected):
    resp = _client().get("/api/v1/auth/me", headers=_auth(world, actor))
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize("path", ["/api/v1/health", "/api/v1/health/live"])
def test_health_requires_no_auth(world, path):
    assert _client().get(path).status_code == 200


# --- IDOR / BOLA ------------------------------------------------------------------


def test_member_cannot_read_cross_project_task(world):
    resp = _client().get(f"/api/v1/tasks/{world['other_task_id']}", headers=auth_headers(world["member_id"]))
    assert resp.status_code == 404, resp.text


def test_member_cannot_list_cross_project_tasks(world):
    resp = _client().get(
        f"/api/v1/projects/{world['other_project_id']}/tasks", headers=auth_headers(world["member_id"])
    )
    assert resp.status_code == 404, resp.text


def test_manager_cannot_view_unrelated_project_members(world):
    resp = _client().get(
        f"/api/v1/projects/{world['other_project_id']}/members", headers=auth_headers(world["manager_id"])
    )
    assert resp.status_code == 404, resp.text


def test_manager_cannot_update_cross_project_task(world):
    resp = _client().patch(
        f"/api/v1/tasks/{world['other_task_id']}", headers=auth_headers(world["manager_id"]), json={"title": "Nope"}
    )
    assert resp.status_code == 404, resp.text


def test_member_cannot_read_peer_task_same_project(world):
    with SessionLocal() as db:
        peer_task = Task(
            project_id=world["project_id"],
            issue_number=2,
            issue_key="ALPHA-2",
            title="Peer task",
            status=TaskStatus.TODO.value,
            created_by=world["manager_id"],
            assignee_id=world["peer_member_id"],
        )
        db.add(peer_task)
        db.commit()
        peer_task_id = peer_task.id

    client = _client()
    denied = client.get(f"/api/v1/tasks/{peer_task_id}", headers=auth_headers(world["member_id"]))
    assert denied.status_code == 404, denied.text
    allowed = client.get(f"/api/v1/tasks/{peer_task_id}", headers=auth_headers(world["manager_id"]))
    assert allowed.status_code == 200, allowed.text
