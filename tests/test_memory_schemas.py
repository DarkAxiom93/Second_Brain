"""Unit tests for Memory API schemas."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.memory import MemoryCreate, MemoryRead


def test_memory_create_accepts_and_trims_valid_input() -> None:
    project_id = uuid.uuid4()
    memory = MemoryCreate(
        project_id=project_id, content="  useful fact  ", source="  note  "
    )
    assert memory.model_dump() == {
        "project_id": project_id,
        "content": "useful fact",
        "source": "note",
    }


@pytest.mark.parametrize("content", ["", "   "])
def test_memory_create_rejects_blank_content(content: str) -> None:
    with pytest.raises(ValidationError):
        MemoryCreate(content=content)


@pytest.mark.parametrize("source", ["", "   ", "x" * 101])
def test_memory_create_rejects_invalid_source(source: str) -> None:
    with pytest.raises(ValidationError):
        MemoryCreate(content="fact", source=source)


def test_memory_create_accepts_100_character_source() -> None:
    assert MemoryCreate(content="fact", source="x" * 100).source == "x" * 100


def test_memory_create_does_not_accept_generated_fields() -> None:
    with pytest.raises(ValidationError):
        MemoryCreate(content="fact", id=uuid.uuid4(), created_at=datetime.now(UTC))


def test_memory_read_serializes_attribute_object() -> None:
    memory_id = uuid.uuid4()
    timestamp = datetime.now(UTC)
    result = MemoryRead.model_validate(
        SimpleNamespace(
            id=memory_id,
            project_id=None,
            content="fact",
            source=None,
            created_at=timestamp,
            updated_at=timestamp,
        )
    )
    assert result.model_dump() == {
        "id": memory_id,
        "project_id": None,
        "content": "fact",
        "source": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
