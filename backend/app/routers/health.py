from fastapi import APIRouter
from sqlalchemy import text

from app.dependencies import DbSession

router = APIRouter(prefix="/health", tags=["상태 확인"])


@router.get("")
def health() -> dict[str, str]:
    """Liveness: does not depend on MySQL availability."""
    return {"status": "ok"}


@router.get("/db")
def database_health(db: DbSession) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
