"""PostgreSQL integration tests for the Memory repository."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models.memory import Memory
from app.models.project import Project
from app.repositories.memories import (
    create_memory,
    get_memory,
    list_memories,
    project_exists,
)
from app.schemas.memory import MemoryCreate
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_memories(
    migrated_test_database: None,
    test_database_url: str,
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()
    yield
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()


def test_create_memory_supports_unassigned_and_duplicate_content() -> None:
    with Session(get_engine()) as session:
        first = create_memory(session, MemoryCreate(content="repeated"))
        second = create_memory(session, MemoryCreate(content="repeated"))
        assert first.id != second.id
        assert first.project_id is None
        session.commit()


def test_create_memory_supports_existing_project() -> None:
    with Session(get_engine()) as session:
        project = Project(name="Pure Axiom")
        session.add(project)
        session.flush()
        assert project_exists(session, project.id)
        assert not project_exists(session, uuid.uuid4())
        memory = create_memory(
            session,
            MemoryCreate(project_id=project.id, content="fact", source="note"),
        )
        assert memory.project_id == project.id
        assert memory.created_at.tzinfo is not None
        assert memory.updated_at.tzinfo is not None
        session.commit()


def test_list_and_get_memories_apply_filter_order_and_pagination() -> None:
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    with Session(get_engine()) as session:
        project = Project(name="Pure Axiom")
        session.add(project)
        session.flush()
        unassigned = Memory(content="unassigned", created_at=base_time)
        older = Memory(
            project_id=project.id,
            content="older",
            created_at=base_time + timedelta(minutes=1),
        )
        newer = Memory(
            project_id=project.id,
            content="newer",
            created_at=base_time + timedelta(minutes=2),
        )
        session.add_all([unassigned, older, newer])
        session.commit()

        assert [
            item.content
            for item in list_memories(session, project_id=None, limit=50, offset=0)
        ] == ["newer", "older", "unassigned"]
        assert [
            item.content
            for item in list_memories(session, project_id=project.id, limit=1, offset=1)
        ] == ["older"]
        assert list_memories(session, project_id=uuid.uuid4(), limit=50, offset=0) == []
        assert get_memory(session, newer.id) is newer
        assert get_memory(session, uuid.uuid4()) is None
