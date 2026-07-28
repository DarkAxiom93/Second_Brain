"""Metadata-only tests for Project and Memory models."""

import importlib

from sqlalchemy.orm import RelationshipProperty

from app.db.base import Base
from app.db.session import get_engine, reset_database_state
from app.models import Memory, Project


def test_metadata_contains_only_approved_tables() -> None:
    assert set(Base.metadata.tables) == {"projects", "memories"}


def test_project_name_is_not_unique() -> None:
    assert Project.__table__.c.name.unique in (None, False)


def test_memory_column_nullability() -> None:
    assert Memory.__table__.c.project_id.nullable is True
    assert Memory.__table__.c.content.nullable is False


def test_models_have_no_embedding_or_vector_columns() -> None:
    for table in (Project.__table__, Memory.__table__):
        assert "embedding" not in table.c
        assert all("vector" not in column.name.lower() for column in table.c)


def test_relationships_do_not_delete_memories() -> None:
    relationship = Project.memories.property

    assert isinstance(relationship, RelationshipProperty)
    assert "delete" not in relationship.cascade
    assert "delete-orphan" not in relationship.cascade
    assert relationship.passive_deletes is True


def test_importing_models_does_not_create_engine() -> None:
    reset_database_state()

    importlib.import_module("app.models.project")
    importlib.import_module("app.models.memory")

    assert get_engine.cache_info().currsize == 0
