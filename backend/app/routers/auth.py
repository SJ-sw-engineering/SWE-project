from datetime import timedelta
import hmac
from typing import Annotated
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.dependencies import AppSettings, CurrentUser, DbSession, bearer, unauthorized
from app.models import AuthSession, User
from app.schemas import LoginRequest, LoginResponse, MessageResponse, RefreshRequest, SignupRequest, UserResponse
from app.security import DUMMY_HASH, create_token, decode_token, hash_password, token_hash, utc_now, verify_password

router = APIRouter(tags=["계정"])


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def token_response(user: User, session: AuthSession, settings: AppSettings) -> LoginResponse:
    now = utc_now()
    access_expiry = min(now + timedelta(minutes=settings.access_token_expire_minutes), session.expires_at)
    return LoginResponse(
        access_token=create_token(user.username, session.id, settings, "access", access_expiry),
        expires_in=max(1, int((access_expiry - now).total_seconds())),
        refresh_token=create_token(user.username, session.id, settings, "refresh", session.expires_at),
        refresh_expires_in=max(1, int((session.expires_at - now).total_seconds())),
        user=UserResponse.model_validate(user),
    )


@router.post("/auth/signup", response_model=UserResponse, status_code=201)
def signup(payload: SignupRequest, db: DbSession, response: Response):
    no_store(response)
    if db.get(User, payload.username) is not None:
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다.")
    user = User(username=payload.username, name=payload.name,
                password=hash_password(payload.password.get_secret_value()))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.get(User, payload.username) is not None:
            raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다.") from None
        raise
    db.refresh(user)
    return user


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: DbSession, settings: AppSettings, response: Response):
    no_store(response)
    user = db.get(User, payload.username)
    stored_hash = user.password if user is not None else DUMMY_HASH
    valid = verify_password(payload.password.get_secret_value(), stored_hash)
    if user is None or not valid:
        raise HTTPException(
            status_code=401, detail="학번 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    now = utc_now()
    session = AuthSession(id=uuid4().hex, username=user.username, created_at=now,
                          expires_at=now + timedelta(days=settings.refresh_token_expire_days))
    result = token_response(user, session, settings)
    session.refresh_token_hash = token_hash(result.refresh_token)
    db.add(session)
    db.commit()
    return result


@router.post("/auth/refresh", response_model=LoginResponse)
def refresh(payload: RefreshRequest, db: DbSession, settings: AppSettings, response: Response):
    no_store(response)
    raw_token = payload.refresh_token.get_secret_value()
    try:
        claims = decode_token(raw_token, settings, "refresh")
    except jwt.InvalidTokenError:
        raise unauthorized() from None
    session = db.scalar(select(AuthSession).where(AuthSession.id == claims["sid"]).with_for_update())
    now = utc_now()
    if (session is None or session.username != claims["sub"]
            or session.revoked_at is not None or session.expires_at <= now):
        raise unauthorized()
    previous_hash = token_hash(raw_token)
    if not hmac.compare_digest(session.refresh_token_hash, previous_hash):
        # A validly signed, previously rotated refresh token was replayed.
        session.revoked_at = now
        db.commit()
        raise unauthorized()
    user = db.get(User, session.username)
    if user is None:
        raise unauthorized()
    result = token_response(user, session, settings)
    changed = db.execute(
        update(AuthSession).where(
            AuthSession.id == session.id,
            AuthSession.refresh_token_hash == previous_hash,
            AuthSession.revoked_at.is_(None), AuthSession.expires_at > now,
        ).values(refresh_token_hash=token_hash(result.refresh_token))
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise unauthorized()
    db.commit()
    return result


@router.post("/auth/logout", response_model=MessageResponse)
def logout(
    db: DbSession, settings: AppSettings, response: Response,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    payload: RefreshRequest | None = None,
):
    """Revoke this login using a refresh body, or an unexpired Bearer access token."""
    no_store(response)
    try:
        if payload is not None:
            claims = decode_token(payload.refresh_token.get_secret_value(), settings, "refresh")
        elif credentials is not None:
            claims = decode_token(credentials.credentials, settings, "access")
        else:
            raise unauthorized()
    except jwt.InvalidTokenError:
        raise unauthorized() from None
    db.execute(update(AuthSession).where(
        AuthSession.id == claims["sid"], AuthSession.username == claims["sub"],
        AuthSession.revoked_at.is_(None),
    ).values(revoked_at=utc_now()).execution_options(synchronize_session=False))
    db.commit()
    return MessageResponse(detail="로그아웃되었습니다.")


@router.get("/users/me", response_model=UserResponse)
def me(user: CurrentUser, response: Response):
    no_store(response)
    return user
