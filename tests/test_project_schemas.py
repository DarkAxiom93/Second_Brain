"""Unit tests for Project API schemas."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.project import ProjectCreate, ProjectRead


def test_project_create_accepts_valid_name() -> None:
    project = ProjectCreate(name="Pure Axiom", description="Mathematics")
    assert project.name == "Pure Axiom"
    assert project.description == "Mathematics"


def test_project_create_trims_surrounding_whitespace() -> None:
    project = ProjectCreate(name="  Pure  Axiom  ")
    assert project.name == "Pure  Axiom"


@pytest.mark.parametrize("name", ["", "   "])
def test_project_create_rejects_blank_names(name: str) -> None:
    with pytest.raises(ValidationError):
        ProjectCreate(name=name)


def test_project_create_rejects_name_longer_than_200_characters() -> None:
    with pytest.raises(ValidationError):
        ProjectCreate(name="x" * 201)


def test_project_create_description_defaults_to_none() -> None:
    assert ProjectCreate(name="Pure Axiom").description is None


def test_project_create_preserves_description_whitespace() -> None:
    project = ProjectCreate(name="Pure Axiom", description="  intentional  ")
    assert project.description == "  intentional  "


def test_project_create_allows_duplicate_names_at_schema_level() -> None:
    first = ProjectCreate(name="Repeated")
    second = ProjectCreate(name="Repeated")
    assert first == second


def test_project_read_serializes_attribute_object() -> None:
    project_id = uuid.uuid4()
    timestamp = datetime.now(UTC)
    source = SimpleNamespace(
        id=project_id,
        name="Pure Axiom",
        description=None,
        created_at=timestamp,
        updated_at=timestamp,
        internal_state="not public",
    )

    result = ProjectRead.model_validate(source)

    assert result.model_dump() == {
        "id": project_id,
        "name": "Pure Axiom",
        "description": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
