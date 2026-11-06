from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from sqlalchemy import exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.dependencies import CurrentUser, DbSession
from app.models import Application, ApprovedMember, Post, User
from app.schemas import (
    ApplicantResponse, ApplicationCreate, ApplicationDecision, ApplicationResponse,
    MyApplicationResponse, PostSummary, TeamResponse,
)
from app.services.recruitment import locked_post, owned_post, sync_size


def private_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(tags=["지원·내 활동"], dependencies=[Depends(private_response)])
PositiveId = Annotated[int, Path(ge=1)]


@router.post("/posts/{post_id}/applications", response_model=ApplicationResponse, status_code=201)
def apply(post_id: PositiveId, payload: ApplicationCreate, user: CurrentUser, db: DbSession):
    post = locked_post(post_id, db)
    if post.author_id == user.username:
        raise HTTPException(status_code=409, detail="자신의 모집글에는 지원할 수 없습니다.")
    existing = db.scalar(select(Application.id).where(
        Application.post_id == post.id, Application.applicant_id == user.username
    ).with_for_update())
    if existing is not None:
        raise HTTPException(status_code=409, detail="이미 지원한 모집글입니다.")
    sync_size(post, db)
    if post.status != "RECRUITING" or post.current_size >= post.target_size:
        raise HTTPException(status_code=409, detail="모집이 마감되었거나 팀 정원이 모두 찼습니다.")
    application = Application(post_id=post.id, applicant_id=user.username,
                              message=payload.message, status="PENDING")
    db.add(application)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.scalar(select(Application.id).where(
            Application.post_id == post_id, Application.applicant_id == user.username
        )) is not None:
            raise HTTPException(status_code=409, detail="이미 지원한 모집글입니다.") from None
        raise
    db.refresh(application)
    return application


@router.get("/posts/{post_id}/applications", response_model=list[ApplicantResponse])
def applicants(post_id: PositiveId, user: CurrentUser, db: DbSession):
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="모집글을 찾을 수 없습니다.")
    if post.author_id != user.username:
        raise HTTPException(status_code=403, detail="팀장만 지원자 목록을 조회할 수 있습니다.")
    rows = db.execute(select(Application, User.name).join(User, Application.applicant_id == User.username)
                      .where(Application.post_id == post.id).order_by(Application.id.asc())).all()
    return [ApplicantResponse(**ApplicationResponse.model_validate(application).model_dump(), name=name)
            for application, name in rows]


@router.patch("/applications/{application_id}", response_model=ApplicationResponse)
def decide(application_id: PositiveId, payload: ApplicationDecision, user: CurrentUser, db: DbSession):
    # Discover the immutable parent ID, then always lock post -> application.
    post_id = db.scalar(select(Application.post_id).where(Application.id == application_id))
    if post_id is None:
        raise HTTPException(status_code=404, detail="지원서를 찾을 수 없습니다.")
    post = owned_post(post_id, user, db)
    application = db.scalar(select(Application).where(Application.id == application_id)
                            .with_for_update().execution_options(populate_existing=True))
    if application is None:
        raise HTTPException(status_code=404, detail="지원서를 찾을 수 없습니다.")
    if application.status != "PENDING":
        raise HTTPException(status_code=409, detail="이미 처리한 지원서입니다.")
    sync_size(post, db)
    if payload.status == "APPROVED":
        # A manually closed team can still review existing pending applications.
        if post.current_size >= post.target_size:
            raise HTTPException(status_code=409, detail="팀 정원이 모두 찼습니다.")
        existing = db.scalar(select(ApprovedMember.id).where(or_(
            (ApprovedMember.post_id == post.id) & (ApprovedMember.member_id == application.applicant_id),
            ApprovedMember.application_id == application.id,
        )).with_for_update().limit(1))
        if existing is not None:
            raise HTTPException(status_code=409, detail="이미 등록된 팀원이거나 승인 정보가 일치하지 않습니다.")
        db.add(ApprovedMember(post_id=post.id, member_id=application.applicant_id,
                              application_id=application.id))
        post.current_size += 1
        if post.current_size >= post.target_size:
            post.status = "CLOSED"
    application.status = payload.status
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # The unique constraints protect against writes from outside this API.
        raise HTTPException(status_code=409, detail="지원 또는 팀원 정보가 충돌했습니다. 다시 조회해 주세요.") from None
    db.refresh(application)
    return application


@router.get("/users/me/applications", response_model=list[MyApplicationResponse])
def my_applications(user: CurrentUser, db: DbSession):
    return db.scalars(select(Application).where(Application.applicant_id == user.username)
                      .options(selectinload(Application.post).selectinload(Post.author))
                      .order_by(Application.id.desc())).all()


@router.get("/users/me/teams", response_model=list[TeamResponse])
def my_teams(user: CurrentUser, db: DbSession):
    membership = exists(select(ApprovedMember.id).where(
        ApprovedMember.post_id == Post.id, ApprovedMember.member_id == user.username
    ))
    posts = db.scalars(select(Post).where(or_(Post.author_id == user.username, membership))
                       .options(selectinload(Post.author))
                       .order_by(Post.created_at.desc(), Post.id.desc())).all()
    return [TeamResponse(**PostSummary.model_validate(post).model_dump(),
                         role="LEADER" if post.author_id == user.username else "MEMBER") for post in posts]
