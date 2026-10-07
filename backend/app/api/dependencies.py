from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import AuthSession, Role, User, utc_now

bearer_scheme = HTTPBearer(auto_error=False)


def get_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise unauthorized
    try:
        claims = decode_access_token(credentials.credentials)
        if claims.get("type") != "access":
            raise unauthorized
        user_id = UUID(claims["sub"])
        session_id = UUID(claims["sid"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise unauthorized from None

    auth_session = db.get(AuthSession, session_id)
    user = db.get(User, user_id)
    if (
        auth_session is None
        or auth_session.user_id != user_id
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= utc_now()
        or user is None
        or not user.is_active
    ):
        raise unauthorized
    return user


def get_current_user(user: User = Depends(get_authenticated_user)) -> User:
    if user.must_change_password:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password change required")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
