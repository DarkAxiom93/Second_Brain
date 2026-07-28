"""Safety fixtures for PostgreSQL integration tests."""

import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.db.session import reset_database_state

TEST_DATABASE_NAME = "second_brain_test"
FORBIDDEN_DATABASE_NAMES = {"second_brain", "postgres", "template0", "template1"}


def validate_test_database_url(database_url: str) -> str:
    """Return a URL only when it targets the one approved test database."""

    database_name = make_url(database_url).database
    if database_name in FORBIDDEN_DATABASE_NAMES or database_name != TEST_DATABASE_NAME:
        raise pytest.UsageError(
            "TEST_DATABASE_URL must target the exact database 'second_brain_test'; "
            "development and unrecognized databases are refused"
        )
    return database_url


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Load the explicit test URL without falling back to DATABASE_URL."""

    value = os.environ.get("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return validate_test_database_url(value)


def verify_connected_test_database(database_url: str) -> None:
    """Verify server identity immediately before destructive migration work."""

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            database_name = connection.scalar(text("SELECT current_database()"))
        if database_name != TEST_DATABASE_NAME:
            raise pytest.UsageError(
                "Connected database is not the approved 'second_brain_test'; "
                "destructive migration work refused"
            )
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def configure_test_database(test_database_url: str) -> Generator[None, None, None]:
    """Point application database access explicitly at the approved test database."""

    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_database_url
    get_settings.cache_clear()
    reset_database_state()
    yield
    reset_database_state()
    get_settings.cache_clear()
    if previous_database_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous_database_url


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    """Return the project Alembic configuration."""

    return Config("alembic.ini")


@pytest.fixture(scope="session")
def migrated_test_database(
    test_database_url: str,
    alembic_config: Config,
) -> Generator[None, None, None]:
    """Rebuild only the verified test database migration state and leave it at head."""

    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_database_url
    get_settings.cache_clear()
    verify_connected_test_database(test_database_url)
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    try:
        yield
    finally:
        command.upgrade(alembic_config, "head")
        get_settings.cache_clear()
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
