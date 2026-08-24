"""Integration tests for the pgvector baseline migration."""

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.db.session import get_engine
from tests.integration.conftest import verify_connected_test_database


def test_alembic_upgrade_reaches_head(migrated_test_database: None) -> None:
    with get_engine().connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))

    assert revision == "0011_automation_persistence"


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


def test_only_approved_application_tables_exist(migrated_test_database: None) -> None:
    tables = set(inspect(get_engine()).get_table_names(schema="public"))

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
    }


def test_migration_graph_has_expected_single_head(
    migrated_test_database: None,
    alembic_config: Config,
) -> None:
    script = ScriptDirectory.from_config(alembic_config)
    assert script.get_heads() == ["0011_automation_persistence"]
    assert script.get_revision("0011_automation_persistence").down_revision == (
        "0010_agent_runtime_persistence"
    )
    assert script.get_revision("0010_agent_runtime_persistence").down_revision == (
        "0009_memory_expiration"
    )
    assert script.get_revision("0008_memory_proposals").down_revision == (
        "0007_source_documents"
    )
    assert script.get_revision("0007_source_documents").down_revision == (
        "0006_memory_embeddings"
    )
    assert script.get_revision("0006_memory_embeddings").down_revision == (
        "0005_memory_search"
    )
    assert script.get_revision("0004_memory_metadata").down_revision == "0003_sources"
    assert script.get_revision("0002_projects_memories").down_revision == (
        "0001_enable_pgvector"
    )


def test_automation_migration_test_database_downgrade_upgrade_lifecycle(
    migrated_test_database: None,
    test_database_url: str,
    alembic_config: Config,
) -> None:
    verify_connected_test_database(test_database_url)
    try:
        command.downgrade(alembic_config, "0010_agent_runtime_persistence")
        assert not inspect(get_engine()).has_table("automations")
        with get_engine().connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0010_agent_runtime_persistence"
            )
    finally:
        command.upgrade(alembic_config, "0011_automation_persistence")
    assert inspect(get_engine()).has_table("automations")
