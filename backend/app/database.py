"""MySQL connection and request-scoped sessions; never auto-create tables."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    # URL.create safely handles passwords containing @, /, or other special characters.
    url = URL.create(
        "mysql+pymysql",
        username=settings.db_user,
        password=settings.db_password.get_secret_value(),
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        query={"charset": "utf8mb4"},
    )
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=5,
        echo=False,
        connect_args={
            "connect_timeout": 5,
            "read_timeout": 10,
            "write_timeout": 10,
            "init_command": "SET time_zone = '+00:00'",
        },
    )


def get_db() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
