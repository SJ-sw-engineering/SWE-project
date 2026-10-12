"""Map the two tables used in phase 1, preserving the supplied SQL names."""

from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, TIMESTAMP, text
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
