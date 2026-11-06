"""Real MySQL locking, timestamp, code and rollback checks; opt-in loopback only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AttendanceRecord, AttendanceSession, Device
from app.security import token_hash, utc_now
from test_mysql_applications import headers, mysql_app, mysql_engine


def device_for(mysql_app):
    leader = headers(mysql_app)
    with TestClient(mysql_app) as client:
        device = client.post("/api/posts/1/devices", headers=leader).json()
    return leader, device, {"X-Device-Key": device["device_credential"]}


def session_for(mysql_app):
    leader, device, key = device_for(mysql_app)
    with TestClient(mysql_app) as client:
        response = client.post("/api/posts/1/attendance-sessions", headers=leader, json={"device_id": device["id"]})
        assert response.status_code == 201
    return leader, device, key, response.json()


def test_mysql_attendance_concurrent_start(mysql_app, mysql_engine):
    leader, device, _key = device_for(mysql_app)
    barrier = Barrier(2)
    def start(_):
        with TestClient(mysql_app) as client:
            barrier.wait(timeout=10)
            return client.post("/api/posts/1/attendance-sessions", headers=leader,
                               json={"device_id": device["id"]}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(start, range(2)))
    assert sorted(results) == [201, 409]
    with Session(mysql_engine) as db:
        assert db.scalar(select(func.count()).select_from(AttendanceSession)) == 1


def test_mysql_concurrent_check_in_is_one_record(mysql_app, mysql_engine):
    _leader, device, key, session = session_for(mysql_app)
    member = headers(mysql_app, "mysql_member_a")
    with TestClient(mysql_app) as client:
        code = client.get(f"/api/devices/{device['id']}/display", headers=key).json()["session"]["code"]
    barrier = Barrier(2)
    def check(_):
        with TestClient(mysql_app) as client:
            barrier.wait(timeout=10)
            result = client.post(f"/api/attendance-sessions/{session['id']}/check-in", headers=member, json={"code": code})
            return result.status_code, result.json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(check, range(2)))
    assert [status for status, _body in results] == [200, 200]
    assert results[0][1] == results[1][1]
    with Session(mysql_engine) as db:
        assert db.scalar(select(func.count()).select_from(AttendanceRecord)) == 1


def test_mysql_lcd_leading_zero_ack_and_expiry(mysql_app, mysql_engine, monkeypatch):
    monkeypatch.setattr("app.routers.attendance.secrets.randbelow", lambda _: 47)
    leader, device, key, session = session_for(mysql_app)
    with TestClient(mysql_app) as client:
        shown = client.get(f"/api/devices/{device['id']}/display", headers=key).json()["session"]
        assert shown["code"] == "000047"
        assert client.post(f"/api/devices/{device['id']}/ack", headers=key, json={"session_id": session["id"]}).status_code == 200
        with Session(mysql_engine) as db:
            row = db.get(AttendanceSession, session["id"])
            assert row.code == "000047" and row.display_ack is True
            assert (row.expiry_time - row.start_time).total_seconds() == 300
            assert db.get(Device, device["id"]).device_credential == "sha256:" + token_hash(device["device_credential"])
            assert db.get(Device, device["id"]).last_ack is not None
            row.expiry_time = utc_now() - timedelta(seconds=1)
            db.commit()
        assert client.get("/api/posts/1/attendance-sessions", headers=leader).json()[0]["status"] == "CLOSED"
        assert client.get(f"/api/devices/{device['id']}/display", headers=key).json()["session"] is None
    with Session(mysql_engine) as db:
        assert db.get(AttendanceSession, session["id"]).status == "CLOSED"


def test_mysql_failed_check_in_insert_leaves_no_partial_record(mysql_app, mysql_engine):
    _leader, device, key, session = session_for(mysql_app)
    member = headers(mysql_app, "mysql_member_a")
    with TestClient(mysql_app) as client:
        code = client.get(f"/api/devices/{device['id']}/display", headers=key).json()["session"]["code"]
    def fail_insert(_connection, _cursor, statement, parameters, _context, _many):
        if statement.lstrip().startswith("INSERT INTO") and "AttendanceRecords" in statement:
            raise IntegrityError("injected attendance insert failure", None, Exception("test only"))
    event.listen(mysql_engine, "before_cursor_execute", fail_insert)
    try:
        with TestClient(mysql_app) as client:
            result = client.post(f"/api/attendance-sessions/{session['id']}/check-in", headers=member, json={"code": code})
            assert result.status_code == 503
            assert code not in result.text
    finally:
        event.remove(mysql_engine, "before_cursor_execute", fail_insert)
    with Session(mysql_engine) as db:
        assert db.scalar(select(func.count()).select_from(AttendanceRecord)) == 0
