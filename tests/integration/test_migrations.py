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

    assert revision == "0016_calendar_event_observations"


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
    inspector = inspect(get_engine())
    tables = set(inspector.get_table_names(schema="public"))

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
    unique_columns = {
        tuple(value["column_names"])
        for value in inspector.get_unique_constraints("external_item_imports")
    }
    assert unique_columns == {("external_item_id",), ("source_document_id",)}
    foreign_keys = {
        (tuple(value["constrained_columns"]), value["referred_table"])
        for value in inspector.get_foreign_keys("external_item_imports")
    }
    assert foreign_keys == {
        (("external_item_id",), "external_items"),
        (("source_document_id",), "source_documents"),
    }
    evidence_column = next(
        value
        for value in inspector.get_columns("calendar_sync_runs")
        if value["name"] == "observation_evidence_version"
    )
    assert evidence_column["nullable"] is True
    assert evidence_column["default"] is None
    observation_uniques = {
        tuple(value["column_names"])
        for value in inspector.get_unique_constraints("calendar_event_observations")
    }
    assert observation_uniques == {("sync_run_id", "occurrence_key")}
    observation_fks = {
        (tuple(value["constrained_columns"]), value["referred_table"])
        for value in inspector.get_foreign_keys("calendar_event_observations")
    }
    assert observation_fks == {
        (
            ("sync_run_id", "calendar_identity_id", "account_revision_id"),
            "calendar_sync_runs",
        ),
        (
            (
                "event_revision_id",
                "account_revision_id",
                "calendar_identity_id",
                "occurrence_key",
            ),
            "calendar_event_revisions",
        ),
    }


def test_migration_graph_has_expected_single_head(
    migrated_test_database: None,
    alembic_config: Config,
) -> None:
    script = ScriptDirectory.from_config(alembic_config)
    assert script.get_heads() == ["0016_calendar_event_observations"]
    assert script.get_revision("0016_calendar_event_observations").down_revision == (
        "0015_calendar_persistence"
    )
    assert script.get_revision("0015_calendar_persistence").down_revision == (
        "0014_connector_refresh_schedules"
    )
    assert script.get_revision("0014_connector_refresh_schedules").down_revision == (
        "0013_external_item_imports"
    )
    assert script.get_revision("0013_external_item_imports").down_revision == (
        "0012_connector_persistence"
    )
    assert script.get_revision("0012_connector_persistence").down_revision == (
        "0011_automation_persistence"
    )
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
        command.upgrade(alembic_config, "head")
    assert inspect(get_engine()).has_table("automations")
