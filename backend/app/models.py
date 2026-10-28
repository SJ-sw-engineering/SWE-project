"""Existing recruitment tables and persistent, revocable login sessions."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "Users"

    username: Mapped[str] = mapped_column(String(20), primary_key=True)
    # The supplied column name is password; store Argon2 hashes in this column.
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP, nullable=True, server_default=text("CURRENT_TIMESTAMP")
    )


class Post(Base):
    __tablename__ = "Posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    author_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("Users.username", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    target_size: Mapped[int] = mapped_column(Integer, nullable=False)
    current_size: Mapped[int | None] = mapped_column(Integer, nullable=True, server_default=text("1"))
    status: Mapped[str | None] = mapped_column(
        Enum("RECRUITING", "CLOSED", name="post_status"),
        nullable=True,
        server_default=text("'RECRUITING'"),
    )
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP, nullable=True, server_default=text("CURRENT_TIMESTAMP")
    )
    author: Mapped[User] = relationship()

    @property
    def author_name(self) -> str:
        return self.author.name


class Application(Base):
    __tablename__ = "Applications"
    __table_args__ = (UniqueConstraint("post_id", "applicant_id", name="uq_applications_post_applicant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("Posts.id", ondelete="CASCADE"))
    applicant_id: Mapped[str] = mapped_column(ForeignKey("Users.username", ondelete="CASCADE"))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(
        Enum("PENDING", "APPROVED", "REJECTED", name="application_status"),
        nullable=True, server_default=text("'PENDING'"),
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP, nullable=True, server_default=text("CURRENT_TIMESTAMP")
    )
    post: Mapped[Post] = relationship()


class ApprovedMember(Base):
    __tablename__ = "ApprovedMembers"
    __table_args__ = (
        UniqueConstraint("post_id", "member_id", name="uq_approved_post_member"),
        UniqueConstraint("application_id", name="uq_approved_application"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("Posts.id", ondelete="CASCADE"))
    member_id: Mapped[str] = mapped_column(ForeignKey("Users.username", ondelete="CASCADE"))
    application_id: Mapped[int] = mapped_column(ForeignKey("Applications.id", ondelete="CASCADE"))


class AuthSession(Base):
    __tablename__ = "AuthSessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    username: Mapped[str] = mapped_column(
        String(20), ForeignKey("Users.username", ondelete="CASCADE"), nullable=False, index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
