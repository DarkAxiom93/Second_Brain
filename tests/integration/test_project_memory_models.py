"""Real PostgreSQL behavior tests for Project and Memory models."""

import uuid
from collections.abc import Generator

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models import Memory, Project
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_model_rows(
    migrated_test_database: None,
    test_database_url: str,
) -> Generator[None, None, None]:
    """Clean only model rows in the verified test database."""

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


def test_duplicate_project_names_are_allowed() -> None:
    with Session(get_engine()) as session:
        session.add_all([Project(name="Repeated"), Project(name="Repeated")])
        session.commit()

        count = len(session.scalars(select(Project)).all())

    assert count == 2


def test_unassigned_memory_can_be_inserted() -> None:
    with Session(get_engine()) as session:
        memory = Memory(content="Independent memory")
        session.add(memory)
        session.commit()
        session.refresh(memory)

        assert memory.project_id is None
        assert memory.project is None


def test_memory_can_be_assigned_to_project_with_typed_values() -> None:
    with Session(get_engine()) as session:
        project = Project(name="Assigned project")
        memory = Memory(content="Assigned memory", project=project)
        session.add(memory)
        session.commit()
        session.refresh(project)
        session.refresh(memory)

        assert memory.project_id == project.id
        assert memory in project.memories
        assert isinstance(project.id, uuid.UUID)
        assert isinstance(memory.id, uuid.UUID)
        assert project.created_at.tzinfo is not None
        assert project.updated_at.tzinfo is not None
        assert memory.created_at.tzinfo is not None
        assert memory.updated_at.tzinfo is not None


def test_deleting_project_preserves_memory_and_nulls_foreign_key() -> None:
    with Session(get_engine()) as session:
        project = Project(name="Temporary project")
        memory = Memory(content="Preserved memory", project=project)
        session.add(memory)
        session.commit()
        memory_id = memory.id

        session.delete(project)
        session.commit()
        session.expire_all()

        preserved = session.get(Memory, memory_id)
        assert preserved is not None
        assert preserved.project_id is None


def test_project_updated_at_changes_after_orm_update() -> None:
    with Session(get_engine()) as session:
        project = Project(name="Before")
        session.add(project)
        session.commit()
        session.refresh(project)
        original_updated_at = project.updated_at

        project.name = "After"
        session.commit()
        session.refresh(project)

        assert project.updated_at > original_updated_at


def test_memory_updated_at_changes_after_orm_update() -> None:
    with Session(get_engine()) as session:
        memory = Memory(content="Before")
        session.add(memory)
        session.commit()
        session.refresh(memory)
        original_updated_at = memory.updated_at

        memory.content = "After"
        session.commit()
        session.refresh(memory)

        assert memory.updated_at > original_updated_at
