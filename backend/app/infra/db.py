from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_config


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine(url: str | None = None, connect_timeout: int = 5) -> Engine:
    return create_engine(
        url or get_config().database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": connect_timeout},
    )


@lru_cache
def _factory(url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(url))


def open_session(url: str | None = None) -> Session:
    """Новая сессия поверх общего пула соединений: `with open_session(url) as db: ...`."""
    return _factory(url or get_config().database_url)()
