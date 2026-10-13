"""Admin user detail and self-service profile update endpoints (Phase 6)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

from support import auth_headers


def _client():
    return TestClient(app)


@pytest.mark.parametrize("actor,expected", [("admin", 200), ("manager", 403), ("member", 403), ("anon", 401)])
def test_get_user_detail_requires_admin(world, actor, expected):
    headers = {} if actor == "anon" else auth_headers(world[f"{actor}_id"])
    resp = _client().get(f"/api/v1/users/{world['member_id']}", headers=headers)
    assert resp.status_code == expected, resp.text


def test_get_user_detail_returns_profile(world):
    resp = _client().get(f"/api/v1/users/{world['member_id']}", headers=auth_headers(world["admin_id"]))
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == str(world["member_id"])


def test_update_own_profile(world):
    client = _client()
    resp = client.patch(
        "/api/v1/users/me", headers=auth_headers(world["member_id"]), json={"full_name": "Renamed Member"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["full_name"] == "Renamed Member"

    me = client.get("/api/v1/auth/me", headers=auth_headers(world["member_id"]))
    assert me.json()["full_name"] == "Renamed Member"


def test_update_profile_rejects_blank_name(world):
    resp = _client().patch("/api/v1/users/me", headers=auth_headers(world["member_id"]), json={"full_name": "   "})
    assert resp.status_code == 422, resp.text
