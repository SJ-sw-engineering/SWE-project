"""Shared database and authenticated-user dependencies."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import AuthSession, User
from app.security import decode_token, utc_now

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
bearer = HTTPBearer(auto_error=False)


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="로그인이 필요하거나 인증 정보가 유효하지 않습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_session(
    db: DbSession,
    settings: AppSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthSession:
    if credentials is None:
        raise unauthorized()
    try:
        claims = decode_token(credentials.credentials, settings, "access")
    except jwt.InvalidTokenError:
        raise unauthorized() from None
    session = db.get(AuthSession, claims["sid"])
    if (session is None or session.username != claims["sub"]
            or session.revoked_at is not None or session.expires_at <= utc_now()):
        raise unauthorized()
    return session


CurrentSession = Annotated[AuthSession, Depends(get_current_session)]


def get_current_user(db: DbSession, session: CurrentSession) -> User:
    user = db.get(User, session.username)
    if user is None:
        raise unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
