from datetime import timedelta
import hmac
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentUser, DbSession
from app.models import ApprovedMember, AttendanceRecord, AttendanceSession, Device, User
from app.schemas import (
    AttendanceCode, AttendanceRecordResponse, AttendanceRosterMember,
    AttendanceSessionResponse, AttendanceStart,
)
from app.security import utc_now
from app.services.attendance import active, expire_sessions, locked_session, member_allowed, session_response
from app.services.recruitment import locked_post, owned_post


def no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(tags=["출석"], dependencies=[Depends(no_store)])
PositiveId = Annotated[int, Path(ge=1)]


@router.post("/posts/{post_id}/attendance-sessions", response_model=AttendanceSessionResponse, status_code=201)
def start_attendance(post_id: PositiveId, payload: AttendanceStart, user: CurrentUser, db: DbSession):
    post = owned_post(post_id, user, db)
    device = db.scalar(select(Device).where(Device.id == payload.device_id)
                       .with_for_update().execution_options(populate_existing=True))
    if device is None or device.post_id != post.id:
        raise HTTPException(status_code=409, detail="팀에 연결된 장치를 선택해 주세요.")
    now = utc_now().replace(microsecond=0)
    expire_sessions(db, post.id, now)
    existing = db.scalar(select(AttendanceSession.id).where(
        AttendanceSession.post_id == post.id, AttendanceSession.status == "OPEN",
        AttendanceSession.expiry_time > now,
    ).with_for_update().limit(1))
    if existing is not None:
        raise HTTPException(status_code=409, detail="이미 진행 중인 출석이 있습니다.")
    session = AttendanceSession(
        post_id=post.id, device_id=device.id, leader_id=user.username,
        code=f"{secrets.randbelow(1000000):06d}", status="OPEN", display_ack=False,
        start_time=now, expiry_time=now + timedelta(minutes=5),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session_response(session)


@router.get("/posts/{post_id}/attendance-sessions", response_model=list[AttendanceSessionResponse])
def sessions(post_id: PositiveId, user: CurrentUser, db: DbSession):
    post = locked_post(post_id, db)
    member_allowed(post, user, db)
    now = utc_now()
    expire_sessions(db, post.id, now)
    rows = db.scalars(select(AttendanceSession).where(AttendanceSession.post_id == post.id)
                     .order_by(AttendanceSession.id.desc()).with_for_update()).all()
    records = db.scalars(select(AttendanceRecord).where(
        AttendanceRecord.session_id.in_([row.id for row in rows]),
        AttendanceRecord.member_id == user.username,
    ).with_for_update()).all() if rows else []
    own_records = {row.session_id: row for row in records}
    result = [session_response(row, own_records.get(row.id), now) for row in rows]
    db.commit()
    return result


@router.post("/attendance-sessions/{session_id}/close", response_model=AttendanceSessionResponse)
def close_attendance(session_id: PositiveId, user: CurrentUser, db: DbSession):
    _post, session = locked_session(session_id, user, db, owner=True)
    session.status = "CLOSED"
    result = session_response(session)
    db.commit()
    return result


@router.get("/attendance-sessions/{session_id}/records", response_model=list[AttendanceRosterMember])
def roster(session_id: PositiveId, user: CurrentUser, db: DbSession):
    post, session = locked_session(session_id, user, db, owner=True)
    if not active(session):
        session.status = "CLOSED"
    members = db.execute(select(ApprovedMember.member_id, User.name)
                         .join(User, User.username == ApprovedMember.member_id)
                         .where(ApprovedMember.post_id == post.id, ApprovedMember.member_id != post.author_id)
                         .order_by(ApprovedMember.id.asc())).all()
    records = db.scalars(select(AttendanceRecord).where(
        AttendanceRecord.session_id == session.id, AttendanceRecord.is_present == 1,
    ).with_for_update()).all()
    by_member = {row.member_id: row for row in records}
    result = [AttendanceRosterMember(member_id=member_id, name=name, record=by_member.get(member_id))
              for member_id, name in members]
    db.commit()
    return result


@router.post("/attendance-sessions/{session_id}/check-in", response_model=AttendanceRecordResponse)
def check_in(session_id: PositiveId, payload: AttendanceCode, user: CurrentUser, db: DbSession, request: Request):
    post, session = locked_session(session_id, user, db)
    member_allowed(post, user, db, allow_leader=False)
    if not active(session):
        session.status = "CLOSED"
        db.commit()
        raise HTTPException(status_code=409, detail="출석 시간이 만료되었거나 종료되었습니다.")
    request.app.state.check_in_limiter.attempt(session.id, user.username)
    if not hmac.compare_digest(session.code, payload.code):
        raise HTTPException(status_code=400, detail="출석 코드가 올바르지 않습니다.")
    record = db.scalar(select(AttendanceRecord).where(
        AttendanceRecord.session_id == session.id, AttendanceRecord.member_id == user.username,
    ).with_for_update())
    if record is None:
        record = AttendanceRecord(session_id=session.id, member_id=user.username,
                                  is_present=1, checked_in_at=utc_now())
        db.add(record)
    elif record.is_present != 1 or record.checked_in_at is None:
        record.is_present = 1
        record.checked_in_at = utc_now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(AttendanceRecord).where(
            AttendanceRecord.session_id == session_id, AttendanceRecord.member_id == user.username,
            AttendanceRecord.is_present == 1,
        ))
        if existing is None:
            raise
        return AttendanceRecordResponse.model_validate(existing)
    db.refresh(record)
    return record
