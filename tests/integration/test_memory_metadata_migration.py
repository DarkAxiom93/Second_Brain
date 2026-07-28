"""PostgreSQL migration and behavior tests for structured Memory metadata."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_engine, reset_database_state
from app.models import Memory, MemorySource, Project, Source
from tests.integration.conftest import verify_connected_test_database

ALLOWED_TYPES = (
    "working",
    "episodic",
    "semantic",
    "decision",
    "procedural",
    "preference",
    "temporary",
)
ALLOWED_STATUSES = ("active", "superseded", "invalid", "archived")
METADATA_COLUMNS = {
    "title",
    "summary",
    "memory_type",
    "importance",
    "confidence",
    "status",
    "event_time",
    "expires_at",
    "supersedes_id",
}


def test_metadata_migration_lifecycle_preserves_rows(
    test_database_url: str, alembic_config: Config
) -> None:
    verify_connected_test_database(test_database_url)
    command.upgrade(alembic_config, "0003_sources")
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM memory_sources"))
        connection.execute(text("DELETE FROM memories"))
        memory_id = uuid.uuid4()
        connection.execute(
            text("INSERT INTO memories (id, content) VALUES (:id, 'legacy')"),
            {"id": memory_id},
        )
    command.upgrade(alembic_config, "0004_memory_metadata")
    with engine.connect() as connection:
        row = (
            connection.execute(
                text("SELECT * FROM memories WHERE id = :id"), {"id": memory_id}
            )
            .mappings()
            .one()
        )
        assert (
            row["memory_type"],
            row["importance"],
            row["confidence"],
            row["status"],
        ) == ("semantic", 0.5, 1.0, "active")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0004_memory_metadata"
        )
    command.downgrade(alembic_config, "0003_sources")
    inspector = inspect(engine)
    assert not (
        METADATA_COLUMNS
        & {column["name"] for column in inspector.get_columns("memories")}
    )
    assert set(inspector.get_table_names()) == {
        "alembic_version",
        "projects",
        "memories",
        "sources",
        "memory_sources",
    }
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
            )
            == 1
        )
    command.upgrade(alembic_config, "head")
    reset_database_state()


def test_metadata_defaults_values_constraints_and_superseding(
    migrated_test_database: None, test_database_url: str
) -> None:
    verify_connected_test_database(test_database_url)
    engine = get_engine()
    inspector = inspect(engine)
    assert {
        column["name"] for column in inspector.get_columns("memories")
    } >= METADATA_COLUMNS
    assert {index["name"] for index in inspector.get_indexes("memories")} >= {
        "ix_memories_memory_type",
        "ix_memories_status",
        "ix_memories_event_time",
        "ix_memories_supersedes_id",
    }
    with Session(engine) as session:
        session.query(MemorySource).delete()
        session.query(Source).delete()
        session.query(Memory).delete()
        session.query(Project).delete()
        session.commit()
        older = Memory(content="older", source="legacy")
        session.add(older)
        session.flush()
        event_time = datetime.now(UTC) - timedelta(days=1)
        expires_at = datetime.now(UTC) + timedelta(days=1)
        newer = Memory(
            content="newer",
            title="Title",
            summary="Summary",
            event_time=event_time,
            expires_at=expires_at,
            supersedes_id=older.id,
        )
        session.add(newer)
        session.commit()
        session.refresh(newer)
        assert (
            newer.memory_type,
            newer.importance,
            newer.confidence,
            newer.status,
        ) == ("semantic", 0.5, 1.0, "active")
        assert newer.title == "Title" and newer.summary == "Summary"
        assert (
            newer.event_time.tzinfo is not None and newer.expires_at.tzinfo is not None
        )
        assert newer.source is None and older.source == "legacy"
        session.delete(older)
        session.commit()
        session.refresh(newer)
        assert newer.supersedes_id is None and newer.status == "active"


@pytest.mark.parametrize(
    "column,value",
    [
        *(("memory_type", value) for value in ALLOWED_TYPES),
        *(("status", value) for value in ALLOWED_STATUSES),
        ("importance", 0.0),
        ("importance", 1.0),
        ("confidence", 0.0),
        ("confidence", 1.0),
    ],
)
def test_allowed_metadata_values_persist(
    migrated_test_database: None, column: str, value: str | float
) -> None:
    with get_engine().begin() as connection:
        memory_id = uuid.uuid4()
        connection.execute(
            text(
                f"INSERT INTO memories (id, content, {column}) "
                "VALUES (:id, 'valid', :value)"
            ),
            {"id": memory_id, "value": value},
        )
        assert (
            connection.scalar(
                text(f"SELECT {column} FROM memories WHERE id = :id"), {"id": memory_id}
            )
            == value
        )


@pytest.mark.parametrize(
    "column,value",
    [
        ("memory_type", "unknown"),
        ("status", "deleted"),
        ("importance", -0.1),
        ("importance", 1.1),
        ("confidence", -0.1),
        ("confidence", 1.1),
    ],
)
def test_invalid_metadata_values_are_rejected(
    migrated_test_database: None, column: str, value: str | float
) -> None:
    with Session(get_engine()) as session:
        session.add(Memory(content="invalid", **{column: value}))
        with pytest.raises(IntegrityError):
            session.commit()
