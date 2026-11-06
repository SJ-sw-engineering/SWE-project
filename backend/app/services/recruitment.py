from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApprovedMember, Post, User


def locked_post(post_id: int, db: Session) -> Post:
    # Every write for one team takes this lock first, including decisions.
    post = db.scalar(select(Post).where(Post.id == post_id).with_for_update()
                     .execution_options(populate_existing=True))
    if post is None:
        raise HTTPException(status_code=404, detail="모집글을 찾을 수 없습니다.")
    return post


def owned_post(post_id: int, user: User, db: Session) -> Post:
    post = locked_post(post_id, db)
    if post.author_id != user.username:
        raise HTTPException(status_code=403, detail="작성자만 모집글을 관리할 수 있습니다.")
    return post


def sync_size(post: Post, db: Session) -> None:
    # A locking read sees current memberships despite an earlier auth snapshot.
    members = db.scalars(select(ApprovedMember.id).where(
        ApprovedMember.post_id == post.id
    ).with_for_update()).all()
    post.current_size = 1 + len(members)
    if post.current_size >= post.target_size:
        post.status = "CLOSED"
