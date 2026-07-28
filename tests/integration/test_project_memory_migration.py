"""Database-shape tests for the Project and Memory migration."""

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.db.session import get_engine, reset_database_state
from tests.integration.conftest import verify_connected_test_database

EXPECTED_PROJECT_COLUMNS = {
    "id": False,
    "name": False,
    "description": True,
    "created_at": False,
    "updated_at": False,
}
EXPECTED_MEMORY_COLUMNS = {
    "id": False,
    "project_id": True,
    "content": False,
    "source": True,
    "created_at": False,
    "updated_at": False,
}


def test_head_and_tables_match_approved_schema(migrated_test_database: None) -> None:
    inspector = inspect(get_engine())
    tables = set(inspector.get_table_names(schema="public"))
    with get_engine().connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))

    assert revision == "0002_projects_memories"
    assert tables == {"alembic_version", "projects", "memories"}


def test_project_and_memory_columns_match_approved_schema(
    migrated_test_database: None,
) -> None:
    inspector = inspect(get_engine())
    project_columns = {
        column["name"]: column["nullable"]
        for column in inspector.get_columns("projects")
    }
    memory_columns = {
        column["name"]: column["nullable"]
        for column in inspector.get_columns("memories")
    }

    assert project_columns == EXPECTED_PROJECT_COLUMNS
    assert memory_columns == EXPECTED_MEMORY_COLUMNS


def test_memory_foreign_key_uses_on_delete_set_null(
    migrated_test_database: None,
) -> None:
    foreign_keys = inspect(get_engine()).get_foreign_keys("memories")

    assert len(foreign_keys) == 1
    assert foreign_keys[0]["referred_table"] == "projects"
    assert foreign_keys[0]["referred_columns"] == ["id"]
    assert foreign_keys[0]["options"]["ondelete"] == "SET NULL"


def test_expected_indexes_exist(migrated_test_database: None) -> None:
    inspector = inspect(get_engine())
    project_indexes = {index["name"] for index in inspector.get_indexes("projects")}
    memory_indexes = {index["name"] for index in inspector.get_indexes("memories")}

    assert project_indexes == {"ix_projects_created_at"}
    assert memory_indexes == {"ix_memories_created_at", "ix_memories_project_id"}


def test_downgrade_to_0001_and_reupgrade_preserve_vector(
    migrated_test_database: None,
    test_database_url: str,
    alembic_config: Config,
) -> None:
    verify_connected_test_database(test_database_url)
    command.downgrade(alembic_config, "0001_enable_pgvector")
    reset_database_state()

    inspector = inspect(get_engine())
    assert inspector.has_table("projects") is False
    assert inspector.has_table("memories") is False
    with get_engine().connect() as connection:
        vector_version = connection.scalar(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
    assert vector_version == "0.8.5"

    command.upgrade(alembic_config, "head")
    reset_database_state()
    assert inspect(get_engine()).has_table("projects")
    assert inspect(get_engine()).has_table("memories")
