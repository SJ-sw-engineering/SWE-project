"""MySQL connection and request-scoped sessions; never auto-create tables."""

from collections.abc import Iterator
from functools import lru_cache
import ssl

from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


def build_connect_args(settings: Settings) -> dict:
    options = {
        "connect_timeout": 5,
        "read_timeout": 10,
        "write_timeout": 10,
        "init_command": "SET time_zone = '+00:00'",
    }
    if settings.db_ssl:
        # Use system-trusted CAs and verify both certificate and server hostname.
        # TiDB Cloud Starter requires TLS; local MySQL can keep DB_SSL=false.
        options["ssl"] = ssl.create_default_context()
    return options


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
        connect_args=build_connect_args(settings),
    )


def get_db() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
