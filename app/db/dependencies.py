"""FastAPI database dependencies."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import get_session_factory


def get_db_session() -> Generator[Session, None, None]:
    """Yield one session per request with explicit transaction ownership."""

    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
