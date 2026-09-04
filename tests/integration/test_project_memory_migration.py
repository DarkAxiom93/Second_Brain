"""Database-shape tests for the Project and Memory migration."""

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.db.session import get_engine

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
    "title": True,
    "summary": True,
    "memory_type": False,
    "importance": False,
    "confidence": False,
    "status": False,
    "event_time": True,
    "expires_at": True,
    "supersedes_id": True,
    "created_at": False,
    "updated_at": False,
    "search_vector": False,
}


def test_head_and_tables_match_approved_schema(migrated_test_database: None) -> None:
    inspector = inspect(get_engine())
    tables = set(inspector.get_table_names(schema="public"))
    with get_engine().connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))

    assert revision == "0016_calendar_event_observations"
    assert tables == {
        "alembic_version",
        "projects",
        "memories",
        "sources",
        "memory_sources",
        "memory_embeddings",
        "source_documents",
        "source_chunks",
        "memory_extraction_runs",
        "memory_proposals",
        "agent_runs",
        "agent_steps",
        "tool_invocations",
        "approval_requests",
        "agent_events",
        "automations",
        "automation_occurrences",
        "automation_notifications",
        "connector_accounts",
        "connector_sync_runs",
        "external_items",
        "external_item_imports",
        "connector_refresh_schedules",
        "connector_refresh_occurrences",
        "connector_refresh_notifications",
        "calendar_account_revisions",
        "calendar_identities",
        "calendar_sync_runs",
        "calendar_event_revisions",
        "calendar_event_observations",
    }


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

    by_column = {key["constrained_columns"][0]: key for key in foreign_keys}
    assert set(by_column) == {"project_id", "supersedes_id"}
    assert by_column["project_id"]["referred_table"] == "projects"
    assert by_column["supersedes_id"]["referred_table"] == "memories"
    assert all(key["options"]["ondelete"] == "SET NULL" for key in by_column.values())


def test_expected_indexes_exist(migrated_test_database: None) -> None:
    inspector = inspect(get_engine())
    project_indexes = {index["name"] for index in inspector.get_indexes("projects")}
    memory_indexes = {index["name"] for index in inspector.get_indexes("memories")}

    assert project_indexes == {"ix_projects_created_at"}
    assert memory_indexes == {
        "ix_memories_created_at",
        "ix_memories_project_id",
        "ix_memories_memory_type",
        "ix_memories_status",
        "ix_memories_event_time",
        "ix_memories_supersedes_id",
        "ix_memories_search_vector",
    }


def test_migration_follows_pgvector_baseline_without_downgrade(
    migrated_test_database: None,
    alembic_config: Config,
) -> None:
    script = ScriptDirectory.from_config(alembic_config)
    revision = script.get_revision("0002_projects_memories")
    assert revision.down_revision == "0001_enable_pgvector"
    with get_engine().connect() as connection:
        vector_version = connection.scalar(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
    assert vector_version == "0.8.5"
