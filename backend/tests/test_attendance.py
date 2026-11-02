from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AttendanceRecord, AttendanceSession, Device
from app.security import token_hash, utc_now


def login(client, username="20191001", password="20000115"):
    result = client.post("/api/auth/login", json={"username": username, "password": password})
    assert result.status_code == 200
    return {"Authorization": "Bearer " + result.json()["access_token"]}


@pytest.fixture
def team(client, monkeypatch):
    monkeypatch.setattr("app.routers.attendance.secrets.randbelow", lambda _: 47)
    leader = login(client)
    member = login(client, "20191002", "19991123")
    post = client.post("/api/posts", headers=leader, json={
        "title": "출석 테스트", "content": "출석", "category": "Web", "target_size": 2,
    }).json()
    post_id = post["id"]
    application = client.post(f"/api/posts/{post_id}/applications", headers=member, json={"message": "지원"}).json()
    assert client.patch(f"/api/applications/{application['id']}", headers=leader, json={"status": "APPROVED"}).status_code == 200
    device_result = client.post(f"/api/posts/{post_id}/devices", headers=leader)
    assert device_result.status_code == 201
    device = device_result.json()
    return {"post_id": post_id, "leader": leader, "member": member, "device_id": device["id"],
            "key": device["device_credential"], "device_headers": {"X-Device-Key": device["device_credential"]}}


def start(client, team):
    response = client.post(f"/api/posts/{team['post_id']}/attendance-sessions", headers=team["leader"],
                           json={"device_id": team["device_id"]})
    assert response.status_code == 201
    return response.json()


def test_full_lcd_ack_check_in_and_history_flow(client, engine, team):
    device_id, post_id = team["device_id"], team["post_id"]
    assert client.get(f"/api/devices/{device_id}/display", headers=team["device_headers"]).json()["session"] is None
    session = start(client, team)
    assert session["status"] == "OPEN" and session["display_ack"] is False
    assert "code" not in session
    display = client.get(f"/api/devices/{device_id}/display", headers=team["device_headers"])
    shown = display.json()["session"]
    assert shown["code"] == "000047"
    assert 0 < shown["expires_in"] <= 300
    assert display.headers["cache-control"] == "no-store"
    for _ in range(2):
        ack = client.post(f"/api/devices/{device_id}/ack", headers=team["device_headers"], json={"session_id": session["id"]})
        assert ack.json() == {"session_id": session["id"], "display_ack": True}
    with Session(engine) as db:
        assert db.get(AttendanceSession, session["id"]).display_ack is True
        assert db.get(Device, device_id).last_ack is not None
        assert db.get(Device, device_id).device_credential == "sha256:" + token_hash(team["key"])
    sessions_url = f"/api/posts/{post_id}/attendance-sessions"
    before = client.get(sessions_url, headers=team["member"]).json()[0]
    assert "code" not in before and before["my_record"] is None
    endpoint = f"/api/attendance-sessions/{session['id']}/check-in"
    record = client.post(endpoint, headers=team["member"], json={"code": "000047"})
    assert record.status_code == 200
    repeated = client.post(endpoint, headers=team["member"], json={"code": "000047"})
    assert repeated.json() == record.json()
    assert record.json()["checked_in_at"].endswith("Z")
    roster = client.get(f"/api/attendance-sessions/{session['id']}/records", headers=team["leader"])
    assert roster.json()[0]["record"]["id"] == record.json()["id"]
    assert client.get(sessions_url, headers=team["member"]).json()[0]["my_record"]["id"] == record.json()["id"]
    for _ in range(2):
        assert client.post(f"/api/attendance-sessions/{session['id']}/close", headers=team["leader"]).json()["status"] == "CLOSED"
    assert client.get(f"/api/devices/{device_id}/display", headers=team["device_headers"]).json()["session"] is None
    assert client.post(endpoint, headers=team["member"], json={"code": "000047"}).status_code == 409
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(AttendanceRecord).where(AttendanceRecord.session_id == session["id"])) == 1


def test_open_session_on_large_device_id_requires_matching_device_key(client, engine, team):
    # TiDB device IDs need not start at 1 or stay small. This is an isolated SQLite DB.
    new_key = "esp_test_only_new_registration_key"
    with Session(engine) as db:
        db.add(Device(id=30002, post_id=team["post_id"],
                      device_credential="sha256:" + token_hash(new_key)))
        db.commit()
    opened = client.post(f"/api/posts/{team['post_id']}/attendance-sessions",
                         headers=team["leader"], json={"device_id": 30002})
    assert opened.status_code == 201 and opened.json()["status"] == "OPEN"
    path = "/api/devices/30002/display"
    wrong_pair = client.get(path, headers=team["device_headers"])
    assert wrong_pair.status_code == 401
    assert "code" not in wrong_pair.json()
    matched_pair = client.get(path, headers={"X-Device-Key": new_key})
    assert matched_pair.status_code == 200
    assert matched_pair.json()["session"]["id"] == opened.json()["id"]
    assert matched_pair.json()["session"]["code"] == "000047"


def test_device_secret_never_in_list_and_user_token_is_not_device_key(client, team):
    path = f"/api/posts/{team['post_id']}/devices"
    listing = client.get(path, headers=team["leader"])
    assert set(listing.json()[0]) == {"id", "post_id", "last_ack"}
    assert team["key"] not in listing.text
    assert client.get(path, headers=team["member"]).status_code == 403
    assert client.post(path, headers=team["member"]).status_code == 403
    display = f"/api/devices/{team['device_id']}/display"
    assert client.get(display, headers=team["leader"]).status_code == 401
    assert client.get(display, headers={"X-Device-Key": "wrong"}).status_code == 401
    assert client.get("/api/devices/999/display", headers=team["device_headers"]).status_code == 401


def test_only_approved_members_view_sessions_and_only_owner_views_roster(client, team):
    session = start(client, team)
    assert client.post("/api/auth/signup", json={"username": "outsider", "name": "외부인", "password": "password-123"}).status_code == 201
    outsider = login(client, "outsider", "password-123")
    history = f"/api/posts/{team['post_id']}/attendance-sessions"
    for endpoint in [history, f"/api/attendance-sessions/{session['id']}/records"]:
        assert client.get(endpoint, headers=outsider).status_code == 403
    endpoint = f"/api/attendance-sessions/{session['id']}/check-in"
    for headers in [outsider, team["leader"]]:
        assert client.post(endpoint, headers=headers, json={"code": "000047"}).status_code == 403
    assert client.get(f"/api/attendance-sessions/{session['id']}/records", headers=team["member"]).status_code == 403
    assert client.post(f"/api/attendance-sessions/{session['id']}/close", headers=team["member"]).status_code == 403
    assert client.post(history, headers=team["member"], json={"device_id": team["device_id"]}).status_code == 403


def test_one_active_session_per_team_and_wrong_team_device(client, team):
    path = f"/api/posts/{team['post_id']}/attendance-sessions"
    another = client.post(f"/api/posts/{team['post_id']}/devices", headers=team["leader"]).json()
    other_team_device = client.post("/api/posts/2/devices", headers=team["member"]).json()
    assert client.post(path, headers=team["leader"], json={"device_id": other_team_device["id"]}).status_code == 409
    first = start(client, team)
    assert client.post(path, headers=team["leader"], json={"device_id": another["id"]}).status_code == 409
    assert client.post(f"/api/attendance-sessions/{first['id']}/close", headers=team["leader"]).status_code == 200
    second = start(client, team)
    assert second["id"] > first["id"]
    rows = client.get(path, headers=team["member"]).json()
    assert [row["id"] for row in rows] == [second["id"], first["id"]]


def test_expiry_closes_database_row_and_clears_display(client, engine, team):
    session = start(client, team)
    with Session(engine) as db:
        db.get(AttendanceSession, session["id"]).expiry_time = utc_now() - timedelta(seconds=1)
        db.commit()
    shown = client.get(f"/api/devices/{team['device_id']}/display", headers=team["device_headers"])
    assert shown.json()["session"] is None
    with Session(engine) as db:
        assert db.get(AttendanceSession, session["id"]).status == "CLOSED"
    assert client.post(f"/api/devices/{team['device_id']}/ack", headers=team["device_headers"], json={"session_id": session["id"]}).status_code == 409
    assert client.post(f"/api/attendance-sessions/{session['id']}/check-in", headers=team["member"], json={"code": "000047"}).status_code == 409
    start(client, team)


def test_stale_ack_and_wrong_device_do_not_ack_new_session(client, team):
    first = start(client, team)
    extra = client.post(f"/api/posts/{team['post_id']}/devices", headers=team["leader"]).json()
    assert client.post(f"/api/devices/{extra['id']}/ack", headers={"X-Device-Key": extra["device_credential"]}, json={"session_id": first["id"]}).status_code == 403
    client.post(f"/api/attendance-sessions/{first['id']}/close", headers=team["leader"])
    second = start(client, team)
    assert client.post(f"/api/devices/{team['device_id']}/ack", headers=team["device_headers"], json={"session_id": first["id"]}).status_code == 409
    assert client.get(f"/api/posts/{team['post_id']}/attendance-sessions", headers=team["leader"]).json()[0]["display_ack"] is False
    assert second["id"] != first["id"]


def test_wrong_codes_are_rate_limited_without_creating_records(client, engine, team):
    session = start(client, team)
    path = f"/api/attendance-sessions/{session['id']}/check-in"
    for _ in range(5):
        assert client.post(path, headers=team["member"], json={"code": "999999"}).status_code == 400
    limited = client.post(path, headers=team["member"], json={"code": "000047"})
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(AttendanceRecord)) == 0


@pytest.mark.parametrize("code", ["123", "1234567", "12a456", " 12345", 47])
def test_code_requires_six_digit_string(client, team, code):
    session = start(client, team)
    assert client.post(f"/api/attendance-sessions/{session['id']}/check-in", headers=team["member"], json={"code": code}).status_code == 422


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/api/posts/1/devices", None), ("POST", "/api/posts/1/devices", None),
    ("GET", "/api/posts/1/attendance-sessions", None),
    ("POST", "/api/posts/1/attendance-sessions", {"device_id": 1}),
    ("POST", "/api/attendance-sessions/1/close", None),
    ("GET", "/api/attendance-sessions/1/records", None),
    ("POST", "/api/attendance-sessions/1/check-in", {"code": "000047"}),
])
def test_attendance_endpoints_require_login(client, method, path, body):
    assert client.request(method, path, **({"json": body} if body else {})).status_code == 401


def test_missing_sessions_and_devices(client, team):
    assert client.post("/api/attendance-sessions/999/close", headers=team["leader"]).status_code == 404
    assert client.get("/api/attendance-sessions/999/records", headers=team["leader"]).status_code == 404
    assert client.post("/api/attendance-sessions/999/check-in", headers=team["member"], json={"code": "000047"}).status_code == 404
    assert client.post(f"/api/posts/{team['post_id']}/attendance-sessions", headers=team["leader"], json={"device_id": 999}).status_code == 409
    assert client.get("/api/posts/999/attendance-sessions", headers=team["leader"]).status_code == 404


def test_prior_absent_record_does_not_mark_present_until_valid_check_in(client, engine, team):
    session = start(client, team)
    with Session(engine) as db:
        db.add(AttendanceRecord(session_id=session["id"], member_id="20191002", is_present=0,
                                 checked_in_at=utc_now() - timedelta(days=1)))
        db.commit()
    assert client.get(f"/api/posts/{team['post_id']}/attendance-sessions", headers=team["member"]).json()[0]["my_record"] is None
    record = client.post(f"/api/attendance-sessions/{session['id']}/check-in", headers=team["member"], json={"code": "000047"})
    assert record.json()["is_present"] == 1
