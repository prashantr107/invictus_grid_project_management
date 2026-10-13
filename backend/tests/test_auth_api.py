"""Auth API integration tests (SRS §3.1/§8.1): login, generic failures, session
rotation/revocation, logout, password change, forced password change, and login
rate limiting.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Role

from support import SessionLocal, auth_headers, make_user

LOGIN = "/api/v1/auth/login"
PASSWORD = "GoodPassw0rd!1"


def _client():
    return TestClient(app)


def _make_login_user(
    email="login@invictusgrid.com", password=PASSWORD, role=Role.MEMBER, active=True, must_change=False
):
    with SessionLocal() as db:
        user = make_user(db, "Login User", email, role, password=password, must_change_password=must_change)
        user.is_active = active
        db.commit()
        db.refresh(user)
        return user.id


def _login(client, email="login@invictusgrid.com", password=PASSWORD):
    return client.post(LOGIN, json={"email": email, "password": password})


def test_login_success_returns_token_and_cookie(world):
    _make_login_user()
    resp = _login(_client())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "login@invictusgrid.com"
    assert resp.cookies.get("igw_refresh")


def test_login_failures_are_generic_and_indistinguishable(world):
    _make_login_user()
    client = _client()
    wrong_password = _login(client, password="WrongPassw0rd!1")
    unknown_email = _login(client, email="nobody@invictusgrid.com")
    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"] == "Invalid email or password"


def test_login_rejects_inactive_user(world):
    _make_login_user(active=False)
    assert _login(_client()).status_code == 401


def test_me_requires_authentication(world):
    assert _client().get("/api/v1/auth/me").status_code == 401


def test_me_returns_identity(world):
    _make_login_user()
    client = _client()
    token = _login(client).json()["access_token"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "login@invictusgrid.com"


def test_refresh_rotates_and_revokes_the_old_token(world):
    _make_login_user()
    client = _client()
    _login(client)
    old_token = client.cookies.get("igw_refresh")

    rotated = client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200, rotated.text
    assert client.cookies.get("igw_refresh") != old_token

    client.cookies.set("igw_refresh", old_token)
    reused = client.post("/api/v1/auth/refresh")
    assert reused.status_code == 401, reused.text


def test_refresh_without_cookie_is_rejected(world):
    _make_login_user()
    assert _client().post("/api/v1/auth/refresh").status_code == 401


def test_logout_revokes_the_session(world):
    _make_login_user()
    client = _client()
    _login(client)
    old_token = client.cookies.get("igw_refresh")

    assert client.post("/api/v1/auth/logout").status_code == 200
    client.cookies.set("igw_refresh", old_token)
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_change_password_rejects_wrong_current(world):
    _make_login_user()
    client = _client()
    token = _login(client).json()["access_token"]
    resp = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "WrongPassw0rd!1", "new_password": "NewPassw0rd!22"},
    )
    assert resp.status_code == 400, resp.text


def test_change_password_rejects_weak_new_password(world):
    _make_login_user()
    client = _client()
    token = _login(client).json()["access_token"]
    resp = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": PASSWORD, "new_password": "weak"},
    )
    assert resp.status_code == 422, resp.text


def test_change_password_success_revokes_sessions(world):
    _make_login_user()
    client = _client()
    token = _login(client).json()["access_token"]

    changed = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": PASSWORD, "new_password": "NewPassw0rd!22"},
    )
    assert changed.status_code == 200, changed.text
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401

    assert _login(_client(), password="NewPassw0rd!22").status_code == 200


def test_forced_password_change_blocks_endpoints_until_cleared(world):
    _make_login_user(must_change=True)
    client = _client()
    token = _login(client).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    blocked = client.get("/api/v1/projects", headers=headers)
    assert blocked.status_code == 403, blocked.text

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "NewPassw0rd!22"},
    )
    assert changed.status_code == 200, changed.text

    new_token = _login(_client(), password="NewPassw0rd!22").json()["access_token"]
    released = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {new_token}"})
    assert released.status_code == 200, released.text


def test_deactivated_user_cannot_keep_using_issued_token(world):
    user_id = _make_login_user(email="temp@invictusgrid.com")
    client = _client()
    token = _login(client, email="temp@invictusgrid.com").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    deactivated = client.patch(
        f"/api/v1/users/{user_id}/status",
        headers=auth_headers(world["admin_id"]),
        json={"is_active": False},
    )
    assert deactivated.status_code == 200, deactivated.text
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_login_is_rate_limited(world):
    client = _client()
    payload = {"email": "nobody@invictusgrid.com", "password": "GoodPassw0rd!1"}
    codes = [client.post(LOGIN, json=payload).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5
    assert codes[5] == 429


@pytest.mark.parametrize("email", ["not-an-email", ""])
def test_login_rejects_malformed_email(world, email):
    assert _login(_client(), email=email).status_code == 422
