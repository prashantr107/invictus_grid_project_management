"""Unit tests for cross-cutting primitives: password/token security helpers and
settings validation (TRD §11/§15). No database or HTTP is involved.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest

from app.core.config import Settings, get_settings
from app.core.security import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)


def test_password_hash_roundtrip():
    encoded = hash_password("GoodPassw0rd!1")
    assert encoded != "GoodPassw0rd!1"
    assert verify_password("GoodPassw0rd!1", encoded)
    assert not verify_password("WrongPassw0rd!1", encoded)


def test_verify_password_rejects_invalid_hash():
    assert not verify_password("anything", "not-a-real-hash")


def test_refresh_token_hash_is_deterministic():
    token = "some-refresh-token"
    assert hash_refresh_token(token) == hash_refresh_token(token)
    assert hash_refresh_token(token) != hash_refresh_token("other")


def test_new_refresh_tokens_are_unique():
    assert len({new_refresh_token() for _ in range(50)}) == 50


def test_access_token_roundtrip_claims():
    user_id, session_id = uuid4(), uuid4()
    token = create_access_token(user_id, session_id)
    claims = decode_access_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["sid"] == str(session_id)
    assert claims["type"] == "access"
    assert claims["exp"] > claims["iat"]


def test_decode_rejects_wrong_secret():
    token = create_access_token(uuid4(), uuid4())
    forged = jwt.encode(
        jwt.decode(token, options={"verify_signature": False}),
        "a-different-secret-that-is-long-enough-1234567890",
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(forged)


def test_decode_rejects_expired_token():
    settings = get_settings()
    expired = datetime.now(timezone.utc) - timedelta(minutes=1)
    token = jwt.encode(
        {"sub": str(uuid4()), "sid": str(uuid4()), "type": "access", "exp": expired},
        settings.jwt_secret_key,
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def _settings(**overrides) -> Settings:
    base = {
        "database_url": "sqlite+pysqlite:///:memory:",
        "jwt_secret_key": "x" * 40,
        "environment": "development",
        "cookie_secure": False,
        "refresh_cookie_samesite": "lax",
    }
    base.update(overrides)
    return Settings(**base)


def test_settings_accepts_valid_configuration():
    settings = _settings()
    assert settings.cors_origins == ["http://localhost:5173"]


def test_settings_rejects_samesite_none_without_secure_cookie():
    with pytest.raises(ValueError):
        _settings(refresh_cookie_samesite="none", cookie_secure=False)


def test_settings_rejects_production_without_secure_cookie():
    with pytest.raises(ValueError):
        _settings(environment="production", cookie_secure=False)


def test_settings_parses_and_trims_cors_origins():
    settings = _settings(frontend_origins="http://a.example, http://b.example ,")
    assert settings.cors_origins == ["http://a.example", "http://b.example"]


def test_settings_requires_long_jwt_secret():
    with pytest.raises(ValueError):
        _settings(jwt_secret_key="too-short")
