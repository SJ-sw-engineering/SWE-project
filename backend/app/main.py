"""Application entry point: python -m uvicorn app.main:app --reload."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.routers import auth, health, posts

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name, version="0.2.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.include_router(health.router)
    application.include_router(auth.router, prefix="/api")
    application.include_router(posts.router, prefix="/api")

    @application.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError):
        # Do not log SQL parameters or raw exceptions (which can contain secrets).
        logger.warning("Database request failed: %s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={"detail": "DB 요청을 처리할 수 없습니다. 연결 정보와 DB 초기화를 확인해 주세요."},
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        # FastAPI's default validation output may echo a submitted password.
        errors = [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    @application.get("/", include_in_schema=False)
    def index():
        return {"name": settings.app_name, "docs": "/docs", "health": "/health"}

    return application


app = create_app()
