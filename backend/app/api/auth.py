from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.dependencies import get_authenticated_user
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, hash_refresh_token, new_refresh_token, verify_password
from app.db.session import get_db
from app.models import AuthSession, User, utc_now
from app.schemas import LoginRequest, MessageResponse, PasswordChange, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["authentication"])
limiter = Limiter(key_func=get_remote_address)
REFRESH_COOKIE = "igw_refresh"
_DUMMY_PASSWORD_HASH = hash_password("TimingOnly-NotARealAccount-93!")


def set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE, token, httponly=True, secure=settings.cookie_secure, samesite=settings.refresh_cookie_samesite,
        max_age=settings.refresh_token_days * 86400, path=f"{settings.api_v1_prefix}/auth",
    )


def check_browser_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin not in get_settings().cors_origins:
        raise HTTPException(status_code=403, detail="Origin not allowed")


def issue_session(user: User, db: Session) -> tuple[str, str]:
    settings = get_settings()
    refresh_token = new_refresh_token()
    auth_session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        expires_at=utc_now() + timedelta(days=settings.refresh_token_days),
    )
    db.add(auth_session)
    db.flush()
    return refresh_token, create_access_token(user.id, auth_session.id)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, response: Response, payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_matches = verify_password(payload.password.get_secret_value(), password_hash)
    if user is None or not user.is_active or not password_matches:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    refresh_token, access_token = issue_session(user, db)
    db.commit()
    set_refresh_cookie(response, refresh_token)
    return TokenResponse(
        access_token=access_token,
        expires_in=get_settings().access_token_minutes * 60,
        user=UserRead.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    settings = get_settings()
    check_browser_origin(request)
    raw_token = request.cookies.get(REFRESH_COOKIE)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    old_session = db.scalar(
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == hash_refresh_token(raw_token))
        .with_for_update()
    )
    user = db.get(User, old_session.user_id) if old_session else None
    if (
        old_session is None or old_session.revoked_at is not None or old_session.expires_at <= utc_now()
        or user is None or not user.is_active
    ):
        response.delete_cookie(REFRESH_COOKIE, path=f"{settings.api_v1_prefix}/auth", secure=settings.cookie_secure, httponly=True, samesite=settings.refresh_cookie_samesite)
        raise HTTPException(status_code=401, detail="Authentication required")

    old_session.revoked_at = utc_now()
    new_token, access_token = issue_session(user, db)
    db.commit()
    set_refresh_cookie(response, new_token)
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_minutes * 60,
        user=UserRead.model_validate(user),
    )


@router.post("/logout", response_model=MessageResponse)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> MessageResponse:
    settings = get_settings()
    check_browser_origin(request)
    raw_token = request.cookies.get(REFRESH_COOKIE)
    if raw_token:
        auth_session = db.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == hash_refresh_token(raw_token)))
        if auth_session and auth_session.revoked_at is None:
            auth_session.revoked_at = utc_now()
            db.commit()
    response.delete_cookie(REFRESH_COOKIE, path=f"{settings.api_v1_prefix}/auth", secure=settings.cookie_secure, httponly=True, samesite=settings.refresh_cookie_samesite)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_authenticated_user)) -> User:
    return user


@router.post("/change-password", response_model=MessageResponse)
def change_password(payload: PasswordChange, db: Session = Depends(get_db), user: User = Depends(get_authenticated_user)) -> MessageResponse:
    current_password = payload.current_password.get_secret_value()
    new_password = payload.new_password.get_secret_value()
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if verify_password(new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Choose a different password")
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    db.commit()
    return MessageResponse(message="Password updated. Sign in again.")
