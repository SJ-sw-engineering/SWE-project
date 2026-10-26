from datetime import timedelta

import jwt
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.main import create_app
from app.models import Application, ApprovedMember, AuthSession, Post, User
from app.security import token_hash, utc_now, verify_password


def login(client, username="20191001", password="20000115"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()


def bearer(tokens):
    return {"Authorization": "Bearer " + tokens["access_token"]}


def test_signup_hashes_password_and_can_login(client, engine):
    body = {"username": "new_student", "name": " 새 학생 ", "password": "test-password-123"}
    response = client.post("/api/auth/signup", json=body)
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["name"] == "새 학생"
    assert set(response.json()) == {"username", "name", "created_at"}
    assert body["password"] not in response.text
    with Session(engine) as db:
        stored = db.get(User, "new_student").password
        assert stored != body["password"]
        assert verify_password(body["password"], stored)
    tokens = login(client, "new_student", body["password"])
    assert client.get("/api/users/me", headers=bearer(tokens)).json()["username"] == "new_student"
    assert client.post("/api/auth/signup", json=body).status_code == 409


@pytest.mark.parametrize("change", [
    {"username": "bad id"}, {"username": "abc"}, {"name": "   "},
    {"password": "s3cr!t"}, {"password_check": "must-not-send-this"},
])
def test_signup_validation(client, change):
    body = {"username": "new_student", "name": "학생", "password": "test-password-123", **change}
    response = client.post("/api/auth/signup", json=body)
    assert response.status_code == 422
    assert body["password"] not in response.text


def test_refresh_rotates_and_only_stores_hash(client, engine):
    first = login(client)
    assert first["refresh_expires_in"] > first["expires_in"]
    with Session(engine) as db:
        session = db.scalar(select(AuthSession))
        assert session.refresh_token_hash == token_hash(first["refresh_token"])
        assert first["refresh_token"] not in session.refresh_token_hash
    response = client.post("/api/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert response.status_code == 200
    second = response.json()
    assert second["access_token"] != first["access_token"]
    assert second["refresh_token"] != first["refresh_token"]
    assert client.get("/api/users/me", headers=bearer(second)).status_code == 200
    with Session(engine) as db:
        assert db.scalar(select(AuthSession)).refresh_token_hash == token_hash(second["refresh_token"])


def test_refresh_replay_revokes_login_but_not_other_login(client):
    first, independent = login(client), login(client)
    second = client.post("/api/auth/refresh", json={"refresh_token": first["refresh_token"]}).json()
    assert client.post("/api/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": second["refresh_token"]}).status_code == 401
    assert client.get("/api/users/me", headers=bearer(first)).status_code == 401
    assert client.get("/api/users/me", headers=bearer(second)).status_code == 401
    assert client.get("/api/users/me", headers=bearer(independent)).status_code == 200


@pytest.mark.parametrize("method", ["bearer", "refresh"])
def test_logout_persists_and_invalidates_access_and_refresh(client, app, method):
    tokens = login(client)
    args = {"headers": bearer(tokens)} if method == "bearer" else {"json": {"refresh_token": tokens["refresh_token"]}}
    assert client.post("/api/auth/logout", **args).status_code == 200
    assert client.post("/api/auth/logout", **args).status_code == 200
    assert client.get("/api/users/me", headers=bearer(tokens)).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    # New application instance, same persistent DB: no process-local blacklist.
    from fastapi.testclient import TestClient
    restarted = create_app()
    restarted.dependency_overrides.update(app.dependency_overrides)
    with TestClient(restarted) as other_client:
        assert other_client.get("/api/users/me", headers=bearer(tokens)).status_code == 401


def test_token_types_and_invalid_refresh_do_not_revoke_valid_session(client):
    tokens = login(client)
    assert client.get("/api/users/me", headers={"Authorization": "Bearer " + tokens["refresh_token"]}).status_code == 401
    for token in [tokens["access_token"], "invalid-token"]:
        assert client.post("/api/auth/refresh", json={"refresh_token": token}).status_code == 401
    assert client.post("/api/auth/logout").status_code == 401
    assert client.get("/api/users/me", headers=bearer(tokens)).status_code == 200


def test_expired_access_can_refresh_and_logout_using_refresh(client, settings):
    tokens = login(client)
    claims = jwt.decode(tokens["access_token"], options={"verify_signature": False})
    claims.update(iat=utc_now() - timedelta(hours=2), exp=utc_now() - timedelta(hours=1))
    expired = jwt.encode(claims, settings.jwt_secret_key.get_secret_value(), algorithm="HS256")
    assert client.get("/api/users/me", headers={"Authorization": "Bearer " + expired}).status_code == 401
    refreshed = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    assert client.post("/api/auth/logout", json={"refresh_token": refreshed.json()["refresh_token"]}).status_code == 200


def test_session_expiry_is_enforced_in_database(client, engine):
    tokens = login(client)
    with Session(engine) as db:
        db.scalar(select(AuthSession)).expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/users/me", headers=bearer(tokens)).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_post_create_edit_close_delete_flow(client, engine):
    headers = bearer(login(client))
    body = {"title": " 새 모집글 ", "content": " 본문 ", "category": "Web/Frontend", "target_size": 4}
    response = client.post("/api/posts", json=body, headers=headers)
    assert response.status_code == 201
    post = response.json()
    assert (post["title"], post["content"], post["current_size"], post["status"]) == ("새 모집글", "본문", 1, "RECRUITING")
    assert "author_id" not in post
    with Session(engine) as db:
        assert db.get(Post, post["id"]).author_id == "20191001"
    path = "/api/posts/" + str(post["id"])
    assert client.get(path + "/context", headers=headers).json() == {"is_owner": True, "my_application": None}
    updated = client.patch(path, json={"title": "수정", "target_size": 2}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["content"] == "본문"
    for _ in range(2):
        assert client.post(path + "/close", headers=headers).json()["status"] == "CLOSED"
    assert client.patch(path, json={"target_size": 10}, headers=headers).json()["status"] == "CLOSED"
    deleted = client.delete(path, headers=headers)
    assert deleted.status_code == 200
    assert deleted.json() == {"detail": "모집글이 삭제되었습니다."}
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("method,path,body", [
    ("post", "/api/posts", {"title": "제목", "content": "본문", "category": "Web", "target_size": 4}),
    ("patch", "/api/posts/1", {"title": "변조"}),
    ("delete", "/api/posts/1", None), ("post", "/api/posts/1/close", None),
])
def test_post_writes_require_authentication(client, method, path, body):
    assert client.request(method, path, **({"json": body} if body else {})).status_code == 401


@pytest.mark.parametrize("method,path,body", [
    ("patch", "/api/posts/1", {"title": "변조"}),
    ("delete", "/api/posts/1", None), ("post", "/api/posts/1/close", None),
])
def test_other_user_cannot_modify_post(client, method, path, body):
    headers = bearer(login(client, "20191002", "19991123"))
    response = client.request(method, path, headers=headers, **({"json": body} if body else {}))
    assert response.status_code == 403
    assert client.get("/api/posts/1").json()["title"] == "웹 프론트엔드 팀원 모집"


@pytest.mark.parametrize("body", [
    {}, {"title": None}, {"title": "   "}, {"content": "x" * 10001},
    {"author_id": "20191002"}, {"current_size": 99}, {"status": "CLOSED"},
    {"target_size": 1}, {"target_size": 101},
])
def test_post_patch_validation_and_no_mass_assignment(client, body):
    headers = bearer(login(client))
    assert client.patch("/api/posts/1", json=body, headers=headers).status_code == 422


def test_capacity_uses_approved_members_and_does_not_reopen(client, engine):
    headers = bearer(login(client, "20191002", "19991123"))
    with Session(engine) as db:
        db.get(Post, 2).current_size = 1  # Simulate a stale cached count.
        db.commit()
    assert client.patch("/api/posts/2", json={"target_size": 2}, headers=headers).status_code == 409
    response = client.patch("/api/posts/2", json={"target_size": 4}, headers=headers)
    assert response.status_code == 200
    assert response.json()["current_size"] == 3
    assert response.json()["status"] == "CLOSED"


def test_reaching_capacity_automatically_closes(client, engine):
    headers = bearer(login(client))
    with Session(engine) as db:
        application = Application(post_id=1, applicant_id="20191002", message="지원", status="APPROVED")
        db.add(application)
        db.flush()
        db.add(ApprovedMember(post_id=1, member_id="20191002", application_id=application.id))
        db.commit()
    response = client.patch("/api/posts/1", json={"target_size": 2}, headers=headers)
    assert response.json()["current_size"] == 2
    assert response.json()["status"] == "CLOSED"


def test_delete_cascades_and_context_preserves_application_privacy(client, engine):
    leader = bearer(login(client, "20191002", "19991123"))
    member = bearer(login(client))
    context = client.get("/api/posts/2/context", headers=member)
    assert context.json() == {"is_owner": False, "my_application": {"id": 1, "status": "APPROVED"}}
    assert client.get("/api/posts/2/context").status_code == 401
    assert "author_id" not in client.get("/api/posts/2").json()
    # Extra existing tables need not have API models for DB cascades to work.
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE Devices (id INTEGER PRIMARY KEY, post_id INTEGER REFERENCES Posts(id) ON DELETE CASCADE)"))
        connection.execute(text("CREATE TABLE AttendanceSessions (id INTEGER PRIMARY KEY, device_id INTEGER REFERENCES Devices(id) ON DELETE CASCADE)"))
        connection.execute(text("CREATE TABLE AttendanceRecords (id INTEGER PRIMARY KEY, session_id INTEGER REFERENCES AttendanceSessions(id) ON DELETE CASCADE)"))
        connection.execute(text("INSERT INTO Devices VALUES (1, 2)"))
        connection.execute(text("INSERT INTO AttendanceSessions VALUES (1, 1)"))
        connection.execute(text("INSERT INTO AttendanceRecords VALUES (1, 1)"))
    assert client.delete("/api/posts/2", headers=leader).status_code == 200
    with Session(engine) as db:
        for model in [Application, ApprovedMember]:
            assert db.scalar(select(func.count()).select_from(model)) == 0
        for table in ["Devices", "AttendanceSessions", "AttendanceRecords"]:
            assert db.scalar(text("SELECT COUNT(*) FROM " + table)) == 0
        assert db.get(Post, 1) is not None


def test_missing_post_and_write_cors(client):
    headers = bearer(login(client))
    assert client.patch("/api/posts/999", json={"title": "수정"}, headers=headers).status_code == 404
    assert client.delete("/api/posts/999", headers=headers).status_code == 404
    assert client.post("/api/posts/999/close", headers=headers).status_code == 404
    assert client.get("/api/posts/999/context", headers=headers).status_code == 404
    for method in ["PATCH", "DELETE"]:
        response = client.options("/api/posts/1", headers={
            "Origin": "http://localhost:5500", "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "authorization,content-type",
        })
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5500"
