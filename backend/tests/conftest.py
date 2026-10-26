"""Independent test DB; never connect to a developer's MySQL database."""

import os
from datetime import datetime

# Set test-only values before importing the application. No real .env secrets are read.
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-that-is-more-than-32-characters"
os.environ["DB_PASSWORD"] = "not-used-by-sqlite-tests"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.database import Base, get_db
from app.main import create_app
from app.models import Application, ApprovedMember, Post, User
from app.security import hash_password


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        jwt_secret_key="test-only-secret-key-that-is-more-than-32-characters",
        db_password="not-used-by-sqlite-tests",
        cors_origins=["http://localhost:5500"],
    )


@pytest.fixture
def engine():
    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    @event.listens_for(test_engine, "connect")
    def enforce_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(test_engine)
    with Session(test_engine) as db:
        db.add_all([
            User(username="20191001", password=hash_password("20000115"), name="학생1"),
            User(username="20191002", password=hash_password("19991123"), name="학생2"),
            User(username="20191003", password="20000305", name="변환 전 계정"),
        ])
        db.flush()
        db.add_all([
            Post(id=1, author_id="20191001", title="웹 프론트엔드 팀원 모집", content="리액트 개발",
                 category="Web/Frontend", target_size=4, current_size=1, status="RECRUITING",
                 created_at=datetime(2026, 10, 1)),
            Post(id=2, author_id="20191002", title="데이터 분석", content="파이썬 스터디",
                 category="Data/AI", target_size=3, current_size=3, status="CLOSED",
                 created_at=datetime(2026, 10, 2)),
            Post(id=3, author_id="20191001", title="100% 참여_스터디", content="리액트 심화",
                 category="Web/Frontend", target_size=2, current_size=1, status="RECRUITING",
                 created_at=datetime(2026, 10, 2)),
        ])
        db.flush()
        db.add_all([
            Application(id=1, post_id=2, applicant_id="20191001", message="지원1", status="APPROVED"),
            Application(id=2, post_id=2, applicant_id="20191003", message="지원2", status="APPROVED"),
        ])
        db.flush()
        db.add_all([
            ApprovedMember(post_id=2, member_id="20191001", application_id=1),
            ApprovedMember(post_id=2, member_id="20191003", application_id=2),
        ])
        db.commit()
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def app(engine, settings):
    application = create_app()

    def override_db():
        with Session(engine) as db:
            yield db

    application.dependency_overrides[get_db] = override_db
    application.dependency_overrides[get_settings] = lambda: settings
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
