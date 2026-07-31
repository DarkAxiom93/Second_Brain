"""PostgreSQL proof for read-only operational diagnostics."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, text

from app.diagnostics.runner import run
from tests.integration.conftest import verify_connected_test_database


def test_complete_test_database_diagnostics_are_read_only(
    migrated_test_database: None,
    test_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify_connected_test_database(test_database_url)
    monkeypatch.setenv("TEST_DATABASE_URL", test_database_url)
    resolver = Mock(side_effect=AssertionError("provider resolution is forbidden"))
    monkeypatch.setattr("app.embeddings.dependencies.get_embedding_provider", resolver)
    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
            before = {
                table: connection.scalar(text(f'SELECT count(*) FROM "{table}"'))
                for table in (
                    "projects",
                    "memories",
                    "memory_embeddings",
                    "sources",
                    "source_documents",
                    "source_chunks",
                    "memory_extraction_runs",
                    "memory_proposals",
                )
            }
        result = run(mode="test", repo_root=Path.cwd())
        with engine.connect() as connection:
            after = {
                table: connection.scalar(text(f'SELECT count(*) FROM "{table}"'))
                for table in before
            }
    finally:
        engine.dispose()
    assert result.diagnostics_status == "healthy"
    assert result.target_database == "second_brain_test"
    assert result.aggregate_counts["Projects"] == before["projects"]
    assert before == after
    assert resolver.call_count == 0
    assert (
        next(item for item in result.checks if item.check_id == "pgvector").status
        == "passed"
    )
    assert (
        next(
            item for item in result.checks if item.check_id == "pending_upgrade"
        ).status
        == "passed"
    )


def test_missing_required_database_object_is_failed(
    migrated_test_database: None,
    test_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify_connected_test_database(test_database_url)
    engine = create_engine(test_database_url)
    try:
        fake_inspector = Mock()
        fake_inspector.get_table_names.return_value = ["alembic_version"]
        monkeypatch.setattr(
            "app.diagnostics.service.inspect", Mock(return_value=fake_inspector)
        )
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            from app.diagnostics.service import inspect_database

            checks, counts = inspect_database(
                connection,
                expected_database="second_brain_test",
                head="0009_memory_expiration",
            )
            connection.rollback()
    finally:
        engine.dispose()
    assert counts == {}
    assert (
        next(item for item in checks if item.check_id == "required_tables").status
        == "failed"
    )
