from fastapi import APIRouter, HTTPException, Response

from app.dependencies import AppSettings, CurrentUser, DbSession
from app.models import User
from app.schemas import LoginRequest, LoginResponse, UserResponse
from app.security import DUMMY_HASH, create_access_token, verify_password

router = APIRouter(tags=["로그인"])


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: DbSession, settings: AppSettings, response: Response):
    user = db.get(User, payload.username)
    stored_hash = user.password if user is not None else DUMMY_HASH
    valid = verify_password(payload.password.get_secret_value(), stored_hash)
    if user is None or not valid:
        raise HTTPException(
            status_code=401,
            detail="학번 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return LoginResponse(
        access_token=create_access_token(user.username, settings),
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.get("/users/me", response_model=UserResponse)
def me(user: CurrentUser, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return user
