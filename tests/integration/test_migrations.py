"""Integration tests for the pgvector baseline migration."""

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text

from app.db.session import get_engine
from tests.integration.conftest import verify_connected_test_database


def test_alembic_upgrade_reaches_head(migrated_test_database: None) -> None:
    with get_engine().connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))

    assert revision == "0001_enable_pgvector"


def test_alembic_version_table_exists(migrated_test_database: None) -> None:
    assert inspect(get_engine()).has_table("alembic_version")


def test_vector_extension_is_installed_at_expected_version(
    migrated_test_database: None,
) -> None:
    with get_engine().connect() as connection:
        version = connection.scalar(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )

    assert version == "0.8.5"


def test_no_application_tables_exist(migrated_test_database: None) -> None:
    tables = set(inspect(get_engine()).get_table_names(schema="public"))

    assert tables == {"alembic_version"}
    assert "projects" not in tables
    assert "memories" not in tables


def test_downgrade_and_upgrade_only_verified_test_database(
    migrated_test_database: None,
    test_database_url: str,
    alembic_config: Config,
) -> None:
    verify_connected_test_database(test_database_url)
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")

    engine: Engine = get_engine()
    with engine.connect() as connection:
        version = connection.scalar(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
    assert version == "0.8.5"
