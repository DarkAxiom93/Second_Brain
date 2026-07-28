"""Lazy synchronous SQLAlchemy engine and session infrastructure."""

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Create and cache an engine without opening a database connection."""

    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Create and cache the request session factory."""

    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def reset_database_state() -> None:
    """Dispose cached connections and clear database factories for tests."""

    get_session_factory.cache_clear()
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
