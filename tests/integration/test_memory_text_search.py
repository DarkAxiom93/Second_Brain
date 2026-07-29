"""PostgreSQL integration coverage for Memory lexical search."""

import uuid
from datetime import UTC, datetime, timedelta

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models import Memory
from app.repositories.memories import list_memories
from tests.integration.conftest import verify_connected_test_database


def test_search_migration_lifecycle_preserves_rows(
    test_database_url: str, alembic_config: Config
) -> None:
    verify_connected_test_database(test_database_url)
    command.downgrade(alembic_config, "0004_memory_metadata")
    memory_id = uuid.uuid4()
    with get_engine().begin() as connection:
        connection.execute(
            text(
                "INSERT INTO memories (id, content, title) "
                "VALUES (:id, 'legacy content', 'Legacy title')"
            ),
            {"id": memory_id},
        )
    command.upgrade(alembic_config, "0005_memory_search")
    inspector = inspect(get_engine())
    assert "search_vector" in {
        column["name"] for column in inspector.get_columns("memories")
    }
    assert "ix_memories_search_vector" in {
        index["name"] for index in inspector.get_indexes("memories")
    }
    with get_engine().connect() as connection:
        assert connection.scalar(
            text("SELECT search_vector IS NOT NULL FROM memories WHERE id=:id"),
            {"id": memory_id},
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM pg_extension WHERE extname='vector'")
            )
            == 1
        )
    command.downgrade(alembic_config, "0004_memory_metadata")
    inspector = inspect(get_engine())
    assert "search_vector" not in {
        column["name"] for column in inspector.get_columns("memories")
    }
    with get_engine().connect() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM memories WHERE id=:id"), {"id": memory_id}
            )
            == 1
        )
    command.upgrade(alembic_config, "head")


def test_search_fields_syntax_ranking_filters_pagination_and_updates(
    migrated_test_database: None,
) -> None:
    now = datetime.now(UTC)
    project_id = uuid.uuid4()
    with get_engine().begin() as connection:
        connection.execute(
            text("INSERT INTO projects (id, name) VALUES (:id, 'Search project')"),
            {"id": project_id},
        )
    rows = [
        Memory(
            title="Alpha rocket",
            content="neutral",
            project_id=project_id,
            importance=0.9,
            confidence=0.8,
            memory_type="decision",
            status="active",
            event_time=now,
        ),
        Memory(summary="alpha quoted phrase", content="neutral"),
        Memory(content="alpha beta content"),
        Memory(content="neutral", source="alpha legacy"),
        Memory(content="unrelated"),
        Memory(title=None, summary=None, content="nullable alpha", source=None),
    ]
    with Session(get_engine()) as session:
        session.add_all(rows)
        session.commit()
        title_id = rows[0].id
        assert (
            list_memories(session, project_id=None, query="ALPHA", limit=50, offset=0)[
                0
            ].id
            == title_id
        )
        assert (
            len(
                list_memories(
                    session,
                    project_id=None,
                    query='"quoted phrase"',
                    limit=50,
                    offset=0,
                )
            )
            == 1
        )
        assert (
            len(
                list_memories(
                    session,
                    project_id=None,
                    query="alpha OR unrelated",
                    limit=50,
                    offset=0,
                )
            )
            == 6
        )
        assert (
            len(
                list_memories(
                    session, project_id=None, query="alpha -beta", limit=50, offset=0
                )
            )
            == 4
        )
        assert (
            len(
                list_memories(
                    session, project_id=None, query="alpha beta", limit=50, offset=0
                )
            )
            == 1
        )
        filtered = list_memories(
            session,
            project_id=project_id,
            query="alpha",
            memory_type="decision",
            status="active",
            importance_min=0.8,
            confidence_min=0.7,
            event_time_from=now - timedelta(minutes=1),
            event_time_to=now + timedelta(minutes=1),
            limit=1,
            offset=0,
        )
        assert [item.id for item in filtered] == [title_id]
        assert (
            len(
                list_memories(
                    session, project_id=None, query="alpha", limit=2, offset=1
                )
            )
            == 2
        )
        rows[4].content = "updated alpha"
        session.commit()
        assert rows[4].id in {
            item.id
            for item in list_memories(
                session, project_id=None, query="alpha", limit=50, offset=0
            )
        }
