"""Migration and PostgreSQL behavior tests for normalized sources."""

import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_engine, reset_database_state
from app.models import Memory, MemorySource, Source
from tests.integration.conftest import verify_connected_test_database


def test_upgrade_from_0002_downgrade_and_reupgrade(
    test_database_url: str, alembic_config: Config
) -> None:
    verify_connected_test_database(test_database_url)
    command.downgrade(alembic_config, "0002_projects_memories")
    assert set(inspect(get_engine()).get_table_names()) == {
        "alembic_version",
        "projects",
        "memories",
    }
    command.upgrade(alembic_config, "0003_sources")
    assert set(inspect(get_engine()).get_table_names()) == {
        "alembic_version",
        "projects",
        "memories",
        "sources",
        "memory_sources",
    }
    command.downgrade(alembic_config, "0002_projects_memories")
    assert set(inspect(get_engine()).get_table_names()) == {
        "alembic_version",
        "projects",
        "memories",
    }
    with get_engine().connect() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
            )
            == 1
        )
    command.upgrade(alembic_config, "head")
    reset_database_state()


def test_source_schema_and_relationship_behavior(
    migrated_test_database: None, test_database_url: str
) -> None:
    verify_connected_test_database(test_database_url)
    inspector = inspect(get_engine())
    assert {column["name"] for column in inspector.get_columns("sources")} == {
        "id",
        "source_type",
        "name",
        "reference",
        "checksum",
        "created_at",
        "updated_at",
    }
    assert {column["name"] for column in inspector.get_columns("memory_sources")} == {
        "id",
        "memory_id",
        "source_id",
        "source_location",
        "created_at",
    }
    with Session(get_engine()) as session:
        session.query(MemorySource).delete()
        session.query(Source).delete()
        session.query(Memory).delete()
        session.commit()

        memory_one = Memory(content="one", source="legacy")
        memory_two = Memory(content="two")
        source_one = Source(source_type="file", name="one", checksum="same")
        source_two = Source(source_type="url", name="two", checksum="same")
        session.add_all([memory_one, memory_two, source_one, source_two])
        session.flush()
        session.add_all(
            [
                MemorySource(memory=memory_one, source=source_one),
                MemorySource(
                    memory=memory_one, source=source_two, source_location="page 2"
                ),
                MemorySource(memory=memory_two, source=source_one),
            ]
        )
        session.commit()
        session.refresh(source_one)

        assert isinstance(source_one.id, uuid.UUID)
        assert source_one.created_at.tzinfo is not None
        assert source_one.updated_at.tzinfo is not None
        assert memory_one.source == "legacy"
        assert len(memory_one.source_links) == 2
        assert len(source_one.memory_links) == 2
        assert memory_one.source_links[0].source_location is None

        session.add(MemorySource(memory=memory_one, source=source_one))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        source_ids = {source_one.id, source_two.id}
        memory_one_id = memory_one.id
        session.delete(memory_one)
        session.commit()
        assert all(
            session.get(Source, source_id) is not None for source_id in source_ids
        )
        assert (
            session.scalar(
                text("SELECT count(*) FROM memory_sources WHERE memory_id = :id"),
                {"id": memory_one_id},
            )
            == 0
        )

        memory_two_id = memory_two.id
        session.delete(source_one)
        session.commit()
        assert session.get(Memory, memory_two_id) is not None
        assert (
            session.scalar(
                text("SELECT count(*) FROM memory_sources WHERE source_id = :id"),
                {"id": source_one.id},
            )
            == 0
        )

    columns = inspector.get_columns("sources") + inspector.get_columns("memory_sources")
    assert all(
        "vector" not in column["name"] and column["name"] != "embedding"
        for column in columns
    )
