from fastapi import APIRouter, Depends, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.api.dependencies import get_authenticated_user
from app.core.config import get_settings
from app.core.errors import AuthenticationError, ForbiddenError
from app.db.session import get_db
from app.models import User
from app.schemas import LoginRequest, MessageResponse, PasswordChange, TokenResponse, UserRead
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["authentication"])
limiter = Limiter(key_func=get_remote_address)
REFRESH_COOKIE = "igw_refresh"


def set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        max_age=settings.refresh_token_days * 86400,
        path=f"{settings.api_v1_prefix}/auth",
    )


def _delete_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        REFRESH_COOKIE,
        path=f"{settings.api_v1_prefix}/auth",
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.refresh_cookie_samesite,
    )


def check_browser_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin not in get_settings().cors_origins:
        raise ForbiddenError("Origin not allowed")


def _token_response(user: User, access_token: str) -> TokenResponse:
    return TokenResponse(
        access_token=access_token,
        expires_in=get_settings().access_token_minutes * 60,
        user=UserRead.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, response: Response, payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user, refresh_token, access_token = auth_service.login(db, str(payload.email), payload.password.get_secret_value())
    set_refresh_cookie(response, refresh_token)
    return _token_response(user, access_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    check_browser_origin(request)
    raw_token = request.cookies.get(REFRESH_COOKIE)
    if not raw_token:
        raise AuthenticationError()
    result = auth_service.rotate(db, raw_token)
    if result is None:
        _delete_refresh_cookie(response)
        raise AuthenticationError()
    user, new_token, access_token = result
    set_refresh_cookie(response, new_token)
    return _token_response(user, access_token)


@router.post("/logout", response_model=MessageResponse)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> MessageResponse:
    check_browser_origin(request)
    raw_token = request.cookies.get(REFRESH_COOKIE)
    if raw_token:
        auth_service.revoke(db, raw_token)
    _delete_refresh_cookie(response)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_authenticated_user)) -> User:
    return user


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: PasswordChange, db: Session = Depends(get_db), user: User = Depends(get_authenticated_user)
) -> MessageResponse:
    auth_service.change_password(
        db,
        user,
        payload.current_password.get_secret_value(),
        payload.new_password.get_secret_value(),
    )
    return MessageResponse(message="Password updated. Sign in again.")
