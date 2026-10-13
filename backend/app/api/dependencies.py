from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.context import actor_id_var
from app.core.errors import AuthenticationError, ForbiddenError, PasswordChangeRequiredError
from app.db.session import get_db
from app.models import Role, User
from app.services import auth as auth_service

bearer_scheme = HTTPBearer(auto_error=False)


def get_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthenticationError()
    user = auth_service.resolve_access_token(db, credentials.credentials)
    actor_id_var.set(str(user.id))
    return user


def get_current_user(user: User = Depends(get_authenticated_user)) -> User:
    if user.must_change_password:
        raise PasswordChangeRequiredError()
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.ADMIN.value:
        raise ForbiddenError("Admin access required")
    return user
