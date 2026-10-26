"""Argon2 password hashes and expiring JWT access tokens."""

from datetime import datetime, timedelta, timezone
import hashlib
from uuid import uuid4

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.config import Settings

password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash("dummy-password-for-unknown-users")


def hash_password(plain_password: str) -> str:
    return password_hash.hash(plain_password)


def verify_password(plain_password: str, stored_hash: str) -> bool:
    try:
        return password_hash.verify(plain_password, stored_hash)
    except (UnknownHashError, ValueError):
        # Plaintext seed passwords are not accepted. Run the migration script first.
        password_hash.verify(plain_password, DUMMY_HASH)
        return False


def utc_now() -> datetime:
    """Database DATETIME values use naive UTC on both MySQL and SQLite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_token(username: str, session_id: str, settings: Settings,
                 token_type: str, expires_at: datetime) -> str:
    now = utc_now()
    payload = {
        "sub": username,
        "iat": now,
        "exp": expires_at,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sid": session_id,
        "jti": uuid4().hex,
        "token_type": token_type,
    }
    return jwt.encode(payload, settings.jwt_secret_key.get_secret_value(), algorithm="HS256")


def create_access_token(username: str, settings: Settings, session_id: str) -> str:
    return create_token(username, session_id, settings, "access",
                        utc_now() + timedelta(minutes=settings.access_token_expire_minutes))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def decode_token(token: str, settings: Settings, token_type: str) -> dict:
    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={"require": ["sub", "iat", "exp", "iss", "aud", "sid", "jti", "token_type"]},
    )
    username = payload["sub"]
    if not isinstance(username, str) or not 1 <= len(username) <= 20:
        raise jwt.InvalidTokenError("Invalid subject")
    session_id = payload["sid"]
    if (payload["token_type"] != token_type or not isinstance(session_id, str)
            or len(session_id) != 32 or not isinstance(payload["jti"], str)):
        raise jwt.InvalidTokenError("Invalid token type or session")
    return payload
