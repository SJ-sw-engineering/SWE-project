from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.dependencies import DbSession
from app.models import Post
from app.schemas import PostDetail, PostPage, PostStatus, PostSummary

router = APIRouter(prefix="/posts", tags=["모집글"])


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


@router.get("/{post_id}", response_model=PostDetail)
def get_post(post_id: Annotated[int, Path(ge=1)], db: DbSession):
    post = db.scalar(select(Post).options(selectinload(Post.author)).where(Post.id == post_id))
    if post is None:
        raise HTTPException(status_code=404, detail="모집글을 찾을 수 없습니다.")
    return post
