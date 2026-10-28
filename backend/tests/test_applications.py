import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Application, ApprovedMember, Post


def auth_headers(client, username="20191001", password="20000115"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def new_post(client, size=3):
    leader = auth_headers(client)
    response = client.post("/api/posts", headers=leader, json={
        "title": "지원 테스트", "content": "테스트 본문", "category": "Web", "target_size": size,
    })
    assert response.status_code == 201
    return response.json()["id"], leader


def new_user(client, username):
    assert client.post("/api/auth/signup", json={
        "username": username, "name": username, "password": "test-password-123",
    }).status_code == 201
    return auth_headers(client, username, "test-password-123")


def test_application_approval_and_activity_flow(client, engine):
    post_id, leader = new_post(client, size=2)
    member = auth_headers(client, "20191002", "19991123")
    path = f"/api/posts/{post_id}/applications"
    response = client.post(path, headers=member, json={"message": " 함께 참여합니다. "})
    assert response.status_code == 201
    application = response.json()
    assert application["message"] == "함께 참여합니다."
    assert application["status"] == "PENDING"
    assert application["applicant_id"] == "20191002"
    assert application["applied_at"].endswith("Z")
    assert response.headers["cache-control"] == "no-store"
    assert client.post(path, headers=member, json={"message": "중복"}).status_code == 409
    listing = client.get(path, headers=leader).json()
    assert listing[0]["name"] == "학생2"
    assert "password" not in str(listing)
    mine = client.get("/api/users/me/applications", headers=member).json()
    assert len(mine) == 1
    assert mine[0]["post"]["id"] == post_id
    assert "author_id" not in mine[0]["post"]
    assert post_id not in [p["id"] for p in client.get("/api/users/me/teams", headers=member).json()]
    approved = client.patch(f"/api/applications/{application['id']}", headers=leader, json={"status": "APPROVED"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    post = client.get(f"/api/posts/{post_id}").json()
    assert (post["current_size"], post["status"]) == (2, "CLOSED")
    for headers, role in [(leader, "LEADER"), (member, "MEMBER")]:
        team = next(p for p in client.get("/api/users/me/teams", headers=headers).json() if p["id"] == post_id)
        assert team["role"] == role
    assert client.get(f"/api/posts/{post_id}/context", headers=member).json()["my_application"]["status"] == "APPROVED"
    with Session(engine) as db:
        row = db.scalar(select(ApprovedMember).where(ApprovedMember.application_id == application["id"]))
        assert row.post_id == post_id and row.member_id == "20191002"
        assert db.get(Post, post_id).current_size == 2
    assert client.patch(f"/api/applications/{application['id']}", headers=leader, json={"status": "REJECTED"}).status_code == 409
    # Real post deletion must remove new applications/members and activity entries.
    assert client.delete(f"/api/posts/{post_id}", headers=leader).status_code == 200
    assert client.get("/api/users/me/applications", headers=member).json() == []
    with Session(engine) as db:
        assert db.get(Application, application["id"]) is None
        assert db.scalar(select(func.count()).select_from(ApprovedMember).where(ApprovedMember.post_id == post_id)) == 0


def test_rejection_does_not_add_member_and_cannot_reapply(client, engine):
    post_id, leader = new_post(client)
    member = auth_headers(client, "20191002", "19991123")
    path = f"/api/posts/{post_id}/applications"
    application = client.post(path, headers=member, json={"message": "지원"}).json()
    assert client.patch(f"/api/applications/{application['id']}", headers=leader, json={"status": "REJECTED"}).status_code == 200
    assert client.post(path, headers=member, json={"message": "재지원"}).status_code == 409
    assert client.get(f"/api/posts/{post_id}").json()["current_size"] == 1
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ApprovedMember).where(ApprovedMember.post_id == post_id)) == 0


def test_manual_close_allows_pending_decision_but_blocks_new_application(client):
    post_id, leader = new_post(client)
    member = auth_headers(client, "20191002", "19991123")
    outsider = new_user(client, "outsider")
    path = f"/api/posts/{post_id}/applications"
    application = client.post(path, headers=member, json={"message": "지원"}).json()
    assert client.post(f"/api/posts/{post_id}/close", headers=leader).status_code == 200
    assert client.post(path, headers=outsider, json={"message": "새 지원"}).status_code == 409
    assert client.patch(f"/api/applications/{application['id']}", headers=leader, json={"status": "APPROVED"}).status_code == 200
    assert client.get(f"/api/posts/{post_id}").json()["status"] == "CLOSED"


def test_full_team_leaves_later_application_pending_and_allows_reject(client, engine):
    post_id, leader = new_post(client, size=2)
    first = auth_headers(client, "20191002", "19991123")
    second = new_user(client, "other_member")
    path = f"/api/posts/{post_id}/applications"
    ids = [client.post(path, headers=headers, json={"message": "지원"}).json()["id"] for headers in [first, second]]
    assert client.patch(f"/api/applications/{ids[0]}", headers=leader, json={"status": "APPROVED"}).status_code == 200
    assert client.patch(f"/api/applications/{ids[1]}", headers=leader, json={"status": "APPROVED"}).status_code == 409
    with Session(engine) as db:
        assert db.get(Application, ids[1]).status == "PENDING"
        assert db.get(Post, post_id).current_size == 2
        assert db.scalar(select(func.count()).select_from(ApprovedMember).where(ApprovedMember.post_id == post_id)) == 1
    assert client.patch(f"/api/applications/{ids[1]}", headers=leader, json={"status": "REJECTED"}).status_code == 200


def test_ownership_and_private_activity(client):
    post_id, leader = new_post(client)
    member = auth_headers(client, "20191002", "19991123")
    path = f"/api/posts/{post_id}/applications"
    assert client.post(path, headers=leader, json={"message": "자기 지원"}).status_code == 409
    application = client.post(path, headers=member, json={"message": "비공개 지원 동기"}).json()
    assert client.get(path, headers=member).status_code == 403
    assert client.patch(f"/api/applications/{application['id']}", headers=member, json={"status": "APPROVED"}).status_code == 403
    assert client.get("/api/users/me/applications", headers=leader).json()[0]["id"] != application["id"]
    assert "비공개 지원 동기" not in client.get(f"/api/posts/{post_id}").text
    assert client.get("/api/users/me/teams", headers=leader).headers["cache-control"] == "no-store"


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/api/posts/1/applications", {"message": "지원"}),
    ("GET", "/api/posts/1/applications", None),
    ("PATCH", "/api/applications/1", {"status": "APPROVED"}),
    ("GET", "/api/users/me/applications", None), ("GET", "/api/users/me/teams", None),
])
def test_all_application_endpoints_require_login(client, method, path, body):
    assert client.request(method, path, **({"json": body} if body else {})).status_code == 401


@pytest.mark.parametrize("body", [{}, {"message": "   "}, {"message": "x" * 5001},
                                      {"message": "지원", "applicant_id": "20191001"},
                                      {"message": "지원", "status": "APPROVED"}])
def test_application_validation(client, body):
    headers = auth_headers(client, "20191002", "19991123")
    assert client.post("/api/posts/1/applications", headers=headers, json=body).status_code == 422


@pytest.mark.parametrize("body", [{"status": "PENDING"}, {"status": "approved"}, {},
                                      {"status": "APPROVED", "member_id": "other"}])
def test_decision_validation(client, body):
    assert client.patch("/api/applications/1", headers=auth_headers(client), json=body).status_code == 422


def test_missing_resources_and_unknown_ids(client):
    headers = auth_headers(client)
    assert client.get("/api/posts/999/applications", headers=headers).status_code == 404
    assert client.post("/api/posts/999/applications", headers=headers, json={"message": "지원"}).status_code == 404
    assert client.patch("/api/applications/999", headers=headers, json={"status": "APPROVED"}).status_code == 404
    assert client.get("/api/users/me/teams", headers=headers).json()


def test_unique_constraints_reject_direct_db_duplicates(engine):
    with Session(engine) as db:
        db.add(Application(post_id=2, applicant_id="20191001", message="중복", status="PENDING"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(ApprovedMember(post_id=2, member_id="20191001", application_id=2))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(ApprovedMember(post_id=1, member_id="20191002", application_id=1))
        with pytest.raises(IntegrityError):
            db.commit()
