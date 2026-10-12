"""Argon2 password hashes and expiring JWT access tokens."""

from datetime import datetime, timedelta, timezone

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


def create_access_token(username: str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(payload, settings.jwt_secret_key.get_secret_value(), algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> str:
    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={"require": ["sub", "iat", "exp", "iss", "aud"]},
    )
    username = payload["sub"]
    if not isinstance(username, str) or not 1 <= len(username) <= 20:
        raise jwt.InvalidTokenError("Invalid subject")
    return username
