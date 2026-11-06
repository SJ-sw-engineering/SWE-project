import hmac
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select

from app.dependencies import CurrentUser, DbSession
from app.models import AttendanceSession, Device
from app.routers.attendance import no_store
from app.schemas import DeviceCreated, DeviceDisplay, DeviceResponse, DisplayAck, DisplayAckResponse, DisplaySession
from app.security import token_hash, utc_now
from app.services.attendance import active, expire_sessions
from app.services.recruitment import locked_post, owned_post

router = APIRouter(tags=["ESP32 장치"], dependencies=[Depends(no_store)])
PositiveId = Annotated[int, Path(ge=1)]
device_key = APIKeyHeader(name="X-Device-Key", scheme_name="DeviceKey", auto_error=False)


def authenticate_device(device_id: PositiveId, db: DbSession,
                        key: Annotated[str | None, Security(device_key)]) -> Device:
    device = db.get(Device, device_id)
    if (key is None or device is None or not hmac.compare_digest(
        device.device_credential.encode("utf-8"), ("sha256:" + token_hash(key)).encode("ascii")
    )):
        raise HTTPException(status_code=401, detail="장치 인증 정보가 유효하지 않습니다.")
    return device


CurrentDevice = Annotated[Device, Depends(authenticate_device)]


def lock_device(device: Device, db: DbSession) -> Device:
    locked_post(device.post_id, db)
    result = db.scalar(select(Device).where(Device.id == device.id)
                       .with_for_update().execution_options(populate_existing=True))
    if result is None:
        raise HTTPException(status_code=404, detail="장치를 찾을 수 없습니다.")
    return result


@router.post("/posts/{post_id}/devices", response_model=DeviceCreated, status_code=201)
def register(post_id: PositiveId, user: CurrentUser, db: DbSession):
    post = owned_post(post_id, user, db)
    credential = "esp_" + secrets.token_urlsafe(32)
    device = Device(post_id=post.id, device_credential="sha256:" + token_hash(credential), last_ack=None)
    db.add(device)
    db.commit()
    db.refresh(device)
    return DeviceCreated(id=device.id, post_id=device.post_id, last_ack=device.last_ack,
                         device_credential=credential)


@router.get("/posts/{post_id}/devices", response_model=list[DeviceResponse])
def devices(post_id: PositiveId, user: CurrentUser, db: DbSession):
    owned_post(post_id, user, db)
    return db.scalars(select(Device).where(Device.post_id == post_id).order_by(Device.id.asc())).all()


@router.get("/devices/{device_id}/display", response_model=DeviceDisplay)
def display(device: CurrentDevice, db: DbSession):
    device = lock_device(device, db)
    now = utc_now()
    expire_sessions(db, device.post_id, now)
    session = db.scalar(select(AttendanceSession).where(
        AttendanceSession.device_id == device.id, AttendanceSession.status == "OPEN",
        AttendanceSession.expiry_time > now,
    ).order_by(AttendanceSession.id.desc()).limit(1).with_for_update())
    result = DeviceDisplay(server_time=now, poll_after_seconds=2 if session else 10,
                           session=DisplaySession(
                               id=session.id, code=session.code, expiry_time=session.expiry_time,
                               expires_in=max(0, int((session.expiry_time - now).total_seconds())),
                               display_ack=bool(session.display_ack),
                           ) if session else None)
    db.commit()
    return result


@router.post("/devices/{device_id}/ack", response_model=DisplayAckResponse)
def acknowledge(payload: DisplayAck, device: CurrentDevice, db: DbSession):
    device = lock_device(device, db)
    session = db.scalar(select(AttendanceSession).where(AttendanceSession.id == payload.session_id)
                        .with_for_update().execution_options(populate_existing=True))
    if session is None:
        raise HTTPException(status_code=404, detail="출석 회차를 찾을 수 없습니다.")
    if session.device_id != device.id or session.post_id != device.post_id:
        raise HTTPException(status_code=403, detail="이 장치에 할당된 출석 회차가 아닙니다.")
    if not active(session):
        session.status = "CLOSED"
        db.commit()
        raise HTTPException(status_code=409, detail="종료된 출석 회차입니다.")
    session.display_ack = True
    device.last_ack = utc_now()
    db.commit()
    return DisplayAckResponse(session_id=payload.session_id)
