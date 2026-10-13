"""Project detail, lifecycle (status) updates, and deletion (Phase 6)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

from support import auth_headers


def _client():
    return TestClient(app)


def _create_project(client, world, key="GAMMA", status="PLANNED"):
    resp = client.post(
        "/api/v1/projects",
        headers=auth_headers(world["admin_id"]),
        json={
            "key": key,
            "name": key,
            "status": status,
            "manager_ids": [str(world["manager_id"])],
            "member_ids": [str(world["member_id"])],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.parametrize(
    "actor,expected",
    [("admin", 200), ("manager", 200), ("member", 200), ("peer_member", 200), ("other_manager", 404), ("anon", 401)],
)
def test_get_project_detail(world, actor, expected):
    key = {"anon": None}.get(actor, actor)
    headers = {} if actor == "anon" else auth_headers(world[f"{key}_id"])
    resp = _client().get(f"/api/v1/projects/{world['project_id']}", headers=headers)
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize("actor,expected", [("admin", 200), ("manager", 403), ("member", 403), ("anon", 401)])
def test_update_project_requires_admin(world, actor, expected):
    headers = {} if actor == "anon" else auth_headers(world[f"{actor}_id"])
    resp = _client().patch(f"/api/v1/projects/{world['project_id']}", headers=headers, json={"name": "Renamed"})
    assert resp.status_code == expected, resp.text


def test_update_project_fields_and_status_lifecycle(world):
    client = _client()
    project = _create_project(client, world)

    renamed = client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=auth_headers(world["admin_id"]),
        json={"name": "Gamma Renamed", "description": "desc", "status": "ACTIVE"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Gamma Renamed"
    assert renamed.json()["status"] == "ACTIVE"

    completed = client.patch(
        f"/api/v1/projects/{project['id']}", headers=auth_headers(world["admin_id"]), json={"status": "COMPLETED"}
    )
    assert completed.json()["status"] == "COMPLETED"

    invalid = client.patch(
        f"/api/v1/projects/{project['id']}", headers=auth_headers(world["admin_id"]), json={"status": "PLANNED"}
    )
    assert invalid.status_code == 409, invalid.text


def test_update_project_rejects_empty_payload(world):
    resp = _client().patch(f"/api/v1/projects/{world['project_id']}", headers=auth_headers(world["admin_id"]), json={})
    assert resp.status_code == 422, resp.text


def test_delete_project_cascades_and_requires_admin(world):
    client = _client()
    project = _create_project(client, world, key="DELTA")

    forbidden = client.delete(f"/api/v1/projects/{project['id']}", headers=auth_headers(world["manager_id"]))
    assert forbidden.status_code == 403, forbidden.text

    deleted = client.delete(f"/api/v1/projects/{project['id']}", headers=auth_headers(world["admin_id"]))
    assert deleted.status_code == 204, deleted.text
    assert client.get(f"/api/v1/projects/{project['id']}", headers=auth_headers(world["admin_id"])).status_code == 404
