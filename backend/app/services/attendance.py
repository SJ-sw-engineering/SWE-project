"""Attendance rules; all writes serialize on the parent post before its device/session."""

from collections import OrderedDict, deque
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import ApprovedMember, AttendanceRecord, AttendanceSession, Post, User
from app.schemas import AttendanceRecordResponse, AttendanceSessionResponse
from app.security import utc_now
from app.services.recruitment import locked_post, owned_post


def active(session: AttendanceSession, now=None) -> bool:
    return session.status == "OPEN" and session.expiry_time > (now or utc_now())


def expire_sessions(db: Session, post_id: int, now) -> None:
    db.execute(update(AttendanceSession).where(
        AttendanceSession.post_id == post_id, AttendanceSession.status == "OPEN",
        AttendanceSession.expiry_time <= now,
    ).values(status="CLOSED").execution_options(synchronize_session=False))


def locked_session(session_id: int, user: User, db: Session, owner=False):
    post_id = db.scalar(select(AttendanceSession.post_id).where(AttendanceSession.id == session_id))
    if post_id is None:
        raise HTTPException(status_code=404, detail="출석 회차를 찾을 수 없습니다.")
    post = owned_post(post_id, user, db) if owner else locked_post(post_id, db)
    session = db.scalar(select(AttendanceSession).where(AttendanceSession.id == session_id)
                        .with_for_update().execution_options(populate_existing=True))
    if session is None:
        raise HTTPException(status_code=404, detail="출석 회차를 찾을 수 없습니다.")
    return post, session


def member_allowed(post: Post, user: User, db: Session, allow_leader=True) -> None:
    if allow_leader and post.author_id == user.username:
        return
    membership = db.scalar(select(ApprovedMember.id).where(
        ApprovedMember.post_id == post.id, ApprovedMember.member_id == user.username
    ).with_for_update())
    if membership is None or (not allow_leader and post.author_id == user.username):
        raise HTTPException(status_code=403, detail="승인된 팀원만 출석 인증과 조회를 할 수 있습니다.")


def record_response(record: AttendanceRecord | None):
    return AttendanceRecordResponse.model_validate(record) if record and record.is_present == 1 else None


def session_response(session: AttendanceSession, record=None, now=None):
    return AttendanceSessionResponse(
        id=session.id, post_id=session.post_id, device_id=session.device_id, leader_id=session.leader_id,
        status="OPEN" if active(session, now) else "CLOSED", display_ack=bool(session.display_ack),
        start_time=session.start_time, expiry_time=session.expiry_time, my_record=record_response(record),
    )


class CheckInLimiter:
    """Bounded process-local limit for the single-worker course deployment."""

    def __init__(self):
        self.entries = OrderedDict()
        self.lock = Lock()

    def attempt(self, session_id: int, member_id: str) -> None:
        now = monotonic()
        key = (session_id, member_id)
        with self.lock:
            # Remove expired keys in access order and cap memory use.
            for old_key in list(self.entries):
                times = self.entries[old_key]
                while times and times[0] <= now - 60:
                    times.popleft()
                if not times:
                    del self.entries[old_key]
            times = self.entries.setdefault(key, deque())
            self.entries.move_to_end(key)
            if len(times) >= 5:
                raise HTTPException(status_code=429, detail="시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.",
                                    headers={"Retry-After": str(max(1, ceil(60 - (now - times[0]))))})
            times.append(now)
            while len(self.entries) > 10000:
                self.entries.popitem(last=False)
