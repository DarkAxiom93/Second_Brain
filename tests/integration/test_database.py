"""Integration tests for SQLAlchemy engine and PostgreSQL connectivity."""

from sqlalchemy import text

from app.db.session import get_engine, reset_database_state


def test_engine_creation_is_lazy() -> None:
    reset_database_state()

    assert get_engine.cache_info().currsize == 0
    get_engine()
    assert get_engine.cache_info().currsize == 1


def test_get_engine_reuses_cached_engine() -> None:
    reset_database_state()

    assert get_engine() is get_engine()


def test_reset_database_state_creates_new_engine() -> None:
    first_engine = get_engine()

    reset_database_state()

    assert get_engine() is not first_engine


def test_postgresql_select_one_succeeds() -> None:
    with get_engine().connect() as connection:
        result = connection.scalar(text("SELECT 1"))

    assert result == 1
