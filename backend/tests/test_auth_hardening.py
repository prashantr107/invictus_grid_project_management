"""Phase 5 auth-hardening tests: proxy-aware rate limiting, rate limits on
refresh/change-password, per-account lockout, refresh-token reuse detection,
login origin check, and Admin-initiated password reset."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.errors import AuthenticationError
from app.core.security import hash_password
from app.main import app
from app.models import Role, User
from app.services import auth as auth_service

from support import SessionLocal, auth_headers, make_user

LOGIN = "/api/v1/auth/login"
PASSWORD = "GoodPassw0rd!1"


def _client():
    return TestClient(app)


def _make_login_user(email="login@invictusgrid.com", password=PASSWORD, role=Role.MEMBER, active=True):
    with SessionLocal() as db:
        user = make_user(db, "Login User", email, role, password=password)
        user.is_active = active
        db.commit()
        db.refresh(user)
        return user.id


def _login(client, email="login@invictusgrid.com", password=PASSWORD):
    return client.post(LOGIN, json={"email": email, "password": password})


def _user_with_password(db, email: str, password: str) -> User:
    user = User(
        email=email,
        full_name="Locked User",
        role=Role.MEMBER.value,
        password_hash=hash_password(password),
        is_active=True,
        must_change_password=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_login_rejects_unknown_origin(world):
    _make_login_user()
    resp = _client().post(
        LOGIN,
        json={"email": "login@invictusgrid.com", "password": PASSWORD},
        headers={"Origin": "http://evil.example"},
    )
    assert resp.status_code == 403


def test_rate_limiter_uses_forwarded_for_when_trusted(world, monkeypatch):
    from app.api import auth as auth_module

    settings = auth_module.get_settings().model_copy(update={"trust_proxy_headers": True})
    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)
    client = _client()
    payload = {"email": "nobody@invictusgrid.com", "password": PASSWORD}

    for _ in range(5):
        assert client.post(LOGIN, json=payload, headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 401
    assert client.post(LOGIN, json=payload, headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 429
    assert client.post(LOGIN, json=payload, headers={"X-Forwarded-For": "9.9.9.9"}).status_code == 401


def test_refresh_is_rate_limited(world):
    _make_login_user()
    client = _client()
    _login(client)
    for _ in range(20):
        assert client.post("/api/v1/auth/refresh").status_code == 200
    assert client.post("/api/v1/auth/refresh").status_code == 429


def test_change_password_is_rate_limited(world):
    _make_login_user()
    client = _client()
    token = _login(client).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"current_password": "WrongPassw0rd!1", "new_password": "NewPassw0rd!22"}

    for _ in range(5):
        assert client.post("/api/v1/auth/change-password", headers=headers, json=payload).status_code == 400
    assert client.post("/api/v1/auth/change-password", headers=headers, json=payload).status_code == 429


def test_repeated_failed_logins_lock_the_account(world):
    with SessionLocal() as db:
        user = _user_with_password(db, "lock@invictusgrid.com", PASSWORD)
        for _ in range(5):
            with pytest.raises(AuthenticationError):
                auth_service.authenticate(db, "lock@invictusgrid.com", "WrongPassw0rd!1")
        with pytest.raises(AuthenticationError):
            auth_service.authenticate(db, "lock@invictusgrid.com", PASSWORD)
        db.expire_all()
        locked = db.get(User, user.id)
        assert locked.locked_until is not None
        assert locked.failed_login_attempts == 0


def test_locked_account_cannot_log_in(world):
    user_id = _make_login_user()
    locked_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    with SessionLocal() as db:
        db.get(User, user_id).locked_until = locked_until
        db.commit()
    assert _login(_client()).status_code == 401


def test_refresh_token_reuse_revokes_the_whole_family(world):
    _make_login_user()
    client = _client()
    _login(client)
    first = client.cookies.get("igw_refresh")

    rotated = client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200, rotated.text
    second = client.cookies.get("igw_refresh")

    client.cookies.set("igw_refresh", first)
    reused = client.post("/api/v1/auth/refresh")
    assert reused.status_code == 401, reused.text

    client.cookies.set("igw_refresh", second)
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_admin_can_reset_another_users_password(world):
    client = _client()
    member_id = world["member_id"]
    resp = client.post(
        f"/api/v1/users/{member_id}/password-reset",
        headers=auth_headers(world["admin_id"]),
        json={"new_password": "ResetPassw0rd!9"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["must_change_password"] is True

    login = _login(client, email="member@invictusgrid.com", password="ResetPassw0rd!9")
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    blocked = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "password_change_required"


def test_admin_password_reset_requires_admin(world):
    client = _client()
    resp = client.post(
        f"/api/v1/users/{world['admin_id']}/password-reset",
        headers=auth_headers(world["member_id"]),
        json={"new_password": "ResetPassw0rd!9"},
    )
    assert resp.status_code == 403


def test_admin_password_reset_rejects_weak_password(world):
    client = _client()
    resp = client.post(
        f"/api/v1/users/{world['member_id']}/password-reset",
        headers=auth_headers(world["admin_id"]),
        json={"new_password": "weak"},
    )
    assert resp.status_code == 422


def test_admin_password_reset_revokes_sessions(world):
    user_id = _make_login_user(email="victim@invictusgrid.com")
    client = _client()
    token = _login(client, email="victim@invictusgrid.com").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    reset = client.post(
        f"/api/v1/users/{user_id}/password-reset",
        headers=auth_headers(world["admin_id"]),
        json={"new_password": "ResetPassw0rd!9"},
    )
    assert reset.status_code == 200, reset.text
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
