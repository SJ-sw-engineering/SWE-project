from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.dependencies import CurrentUser, DbSession
from app.models import Application, Post
from app.schemas import ApplicationContext, MessageResponse, PostContext, PostCreate, PostDetail, PostPage, PostStatus, PostSummary, PostUpdate
from app.services.recruitment import owned_post, sync_size

router = APIRouter(prefix="/posts", tags=["모집글"])
PostId = Annotated[int, Path(ge=1)]


@router.get("", response_model=PostPage)
def list_posts(
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    keyword: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    category: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    status: Annotated[PostStatus | None, Query()] = None,
):
    """Public list; keyword is a literal substring, category is an exact match."""
    filters = []
    if keyword is not None:
        filters.append(or_(
            Post.title.contains(keyword, autoescape=True),
            Post.content.contains(keyword, autoescape=True),
        ))
    if category is not None:
        filters.append(Post.category == category)
    if status is not None:
        filters.append(Post.status == status)
    total = db.scalar(select(func.count()).select_from(Post).where(*filters)) or 0
    statement = (
        select(Post).options(selectinload(Post.author)).where(*filters)
        .order_by(Post.created_at.desc(), Post.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    posts = db.scalars(statement).all()
    return PostPage(
        items=[PostSummary.model_validate(post) for post in posts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=PostDetail, status_code=201)
def create_post(payload: PostCreate, user: CurrentUser, db: DbSession):
    post = Post(**payload.model_dump(), author_id=user.username, current_size=1, status="RECRUITING")
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.patch("/{post_id}", response_model=PostDetail)
def update_post(post_id: PostId, payload: PostUpdate, user: CurrentUser, db: DbSession):
    post = owned_post(post_id, user, db)
    sync_size(post, db)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("target_size", post.target_size) < post.current_size:
        raise HTTPException(status_code=409, detail="팀 정원은 팀장을 포함한 현재 인원보다 작을 수 없습니다.")
    for key, value in changes.items():
        setattr(post, key, value)
    if post.current_size >= post.target_size:
        post.status = "CLOSED"
    db.commit()
    db.refresh(post)
    return post


@router.delete("/{post_id}", response_model=MessageResponse)
def delete_post(post_id: PostId, user: CurrentUser, db: DbSession):
    post = owned_post(post_id, user, db)
    db.delete(post)
    db.commit()
    return MessageResponse(detail="모집글이 삭제되었습니다.")


@router.post("/{post_id}/close", response_model=PostDetail)
def close_post(post_id: PostId, user: CurrentUser, db: DbSession):
    post = owned_post(post_id, user, db)
    sync_size(post, db)
    post.status = "CLOSED"
    db.commit()
    db.refresh(post)
    return post


@router.get("/{post_id}/context", response_model=PostContext)
def post_context(post_id: PostId, user: CurrentUser, db: DbSession, response: Response):
    response.headers["Cache-Control"] = "no-store"
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="모집글을 찾을 수 없습니다.")
    application = db.scalar(select(Application).where(
        Application.post_id == post.id, Application.applicant_id == user.username
    ).order_by(Application.id.desc()).limit(1))
    return PostContext(is_owner=post.author_id == user.username,
                       my_application=ApplicationContext.model_validate(application) if application else None)


@router.get("/{post_id}", response_model=PostDetail)
def get_post(post_id: Annotated[int, Path(ge=1)], db: DbSession):
    post = db.scalar(select(Post).options(selectinload(Post.author)).where(Post.id == post_id))
    if post is None:
        raise HTTPException(status_code=404, detail="모집글을 찾을 수 없습니다.")
    return post
