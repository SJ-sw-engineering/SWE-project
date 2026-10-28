from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import verify_password
from scripts.hash_seed_passwords import migrate_passwords


def test_login_and_me_never_expose_password(client):
    response = client.post("/api/auth/login", json={"username": "20191001", "password": "20000115"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800
    assert set(body["user"]) == {"username", "name", "created_at"}
    assert "20000115" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert body["user"]["created_at"].endswith("Z")
    me = client.get("/api/users/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json() == body["user"]


@pytest.mark.parametrize("username,password", [
    ("20191001", "wrong"), ("unknown", "20000115"), ("20191003", "20000305"),
])
def test_invalid_login_and_unmigrated_seed_are_rejected(client, username, password):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 401
    assert response.json() == {"detail": "학번 또는 비밀번호가 올바르지 않습니다."}


def test_login_validation_does_not_echo_password(client):
    sensitive = "secret-" * 30
    response = client.post("/api/auth/login", json={"username": "20191001", "password": sensitive})
    assert response.status_code == 422
    assert sensitive not in response.text
    assert all("input" not in error for error in response.json()["detail"])


def test_me_requires_login(client):
    assert client.get("/api/users/me").status_code == 401


@pytest.mark.parametrize("case", ["expired", "wrong-key", "wrong-audience", "missing-exp", "unknown-user"])
def test_invalid_tokens_are_rejected(client, settings, case):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "20191001", "iat": now, "exp": now + timedelta(minutes=30),
        "iss": settings.jwt_issuer, "aud": settings.jwt_audience,
    }
    key = settings.jwt_secret_key.get_secret_value()
    if case == "expired":
        payload["iat"] = now - timedelta(hours=2)
        payload["exp"] = now - timedelta(hours=1)
    elif case == "wrong-key":
        key = "different-test-signing-key-that-is-long-enough"
    elif case == "wrong-audience":
        payload["aud"] = "another-app"
    elif case == "missing-exp":
        del payload["exp"]
    else:
        payload["sub"] = "deleted-user"
    token = jwt.encode(payload, key, algorithm="HS256")
    assert client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_public_posts_paginate_and_sort_deterministically(client):
    body = client.get("/api/posts", params={"page_size": 1}).json()
    assert body["total"] == 3
    assert body["items"][0]["id"] == 3
    assert "password" not in body["items"][0]
    assert "author_id" not in body["items"][0]
    assert "content" not in body["items"][0]
    assert client.get("/api/posts", params={"page": 2, "page_size": 1}).json()["items"][0]["id"] == 2
    assert client.get("/api/posts", params={"page": 99}).json()["items"] == []


def test_post_filters_work_together(client):
    body = client.get("/api/posts", params={
        "keyword": "리액트", "category": "Web/Frontend", "status": "RECRUITING",
    }).json()
    assert body["total"] == 2
    assert [post["id"] for post in body["items"]] == [3, 1]


@pytest.mark.parametrize("keyword,total", [("%", 1), ("_", 1), ("' OR 1=1 --", 0)])
def test_search_escapes_wildcards_and_does_not_execute_sql(client, keyword, total):
    response = client.get("/api/posts", params={"keyword": keyword})
    assert response.status_code == 200
    assert response.json()["total"] == total


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 101}, {"status": "INVALID"}])
def test_invalid_query_is_rejected(client, params):
    assert client.get("/api/posts", params=params).status_code == 422


def test_detail_and_not_found(client):
    response = client.get("/api/posts/1")
    assert response.status_code == 200
    assert response.json()["content"] == "리액트 개발"
    assert response.json()["author_name"] == "학생1"
    assert client.get("/api/posts/999").status_code == 404


def test_db_failure_is_safe_and_does_not_break_liveness(client, app):
    def unavailable_db():
        raise OperationalError("SECRET SQL", {"password": "private-db-password"}, Exception("private-db-host"))

    app.dependency_overrides[get_db] = unavailable_db
    assert client.get("/health").status_code == 200
    for endpoint in ["/health/db", "/api/posts"]:
        response = client.get(endpoint)
        assert response.status_code == 503
        assert "private-db" not in response.text
        assert "SECRET SQL" not in response.text


def test_hash_migration_dry_run_then_apply_is_repeatable(engine, client):
    with Session(engine) as db:
        original = db.get(User, "20191001").password
        assert migrate_passwords(db, apply=False) == (1, 2)
        assert db.get(User, "20191003").password == "20000305"
        assert migrate_passwords(db, apply=True) == (1, 2)
    with Session(engine) as db:
        assert db.get(User, "20191001").password == original
        assert verify_password("20000305", db.get(User, "20191003").password)
        assert migrate_passwords(db, apply=True) == (0, 3)
    assert client.post("/api/auth/login", json={"username": "20191003", "password": "20000305"}).status_code == 200


def test_database_health_and_documented_endpoints(client):
    assert client.get("/health/db").json() == {"status": "ok", "database": "connected"}
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths) == {
        "/health", "/health/db", "/api/auth/signup", "/api/auth/login", "/api/auth/refresh",
        "/api/auth/logout", "/api/users/me", "/api/posts", "/api/posts/{post_id}",
        "/api/posts/{post_id}/close", "/api/posts/{post_id}/context",
        "/api/posts/{post_id}/applications", "/api/applications/{application_id}",
        "/api/users/me/applications", "/api/users/me/teams",
    }
