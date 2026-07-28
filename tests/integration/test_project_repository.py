"""PostgreSQL integration tests for the Project repository."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models.project import Project
from app.repositories.projects import create_project, list_projects
from app.schemas.project import ProjectCreate
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_projects(
    migrated_test_database: None,
    test_database_url: str,
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Project))
        session.commit()
    yield
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Project))
        session.commit()


def test_create_project_persists_generated_values_and_nullable_description() -> None:
    with Session(get_engine()) as session:
        project = create_project(session, ProjectCreate(name="Pure Axiom"))
        assert session.new or project.id is not None
        session.commit()
        project_id = project.id

    with Session(get_engine()) as session:
        persisted = session.get(Project, project_id)
        assert persisted is not None
        assert isinstance(persisted.id, uuid.UUID)
        assert persisted.description is None
        assert persisted.created_at.tzinfo is not None
        assert persisted.updated_at.tzinfo is not None


def test_duplicate_project_names_can_be_persisted() -> None:
    with Session(get_engine()) as session:
        create_project(session, ProjectCreate(name="Repeated"))
        create_project(session, ProjectCreate(name="Repeated"))
        session.commit()

    with Session(get_engine()) as session:
        assert len(list_projects(session, limit=50, offset=0)) == 2


def test_list_projects_empty_ordered_and_paginated() -> None:
    with Session(get_engine()) as session:
        assert list_projects(session, limit=50, offset=0) == []
        timestamp = datetime.now(UTC)
        first_id = uuid.UUID(int=1)
        second_id = uuid.UUID(int=2)
        older_id = uuid.UUID(int=3)
        session.add_all(
            [
                Project(id=second_id, name="Second", created_at=timestamp),
                Project(
                    id=older_id, name="Older", created_at=timestamp - timedelta(days=1)
                ),
                Project(id=first_id, name="First", created_at=timestamp),
            ]
        )
        session.commit()

        ordered = list_projects(session, limit=50, offset=0)
        limited = list_projects(session, limit=1, offset=0)
        offset = list_projects(session, limit=2, offset=1)

    assert [project.id for project in ordered] == [first_id, second_id, older_id]
    assert [project.id for project in limited] == [first_id]
    assert [project.id for project in offset] == [second_id, older_id]
