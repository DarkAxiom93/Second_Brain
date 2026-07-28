"""Unit tests for Source and MemorySource schemas."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.source import Source
from app.schemas.source import MemorySourceLinkCreate, SourceCreate, SourceRead


def test_source_create_trims_and_normalizes_optional_values() -> None:
    value = SourceCreate(
        source_type=" note ", name=" Notes ", reference=" ", checksum=" abc "
    )
    assert value.model_dump() == {
        "source_type": "note",
        "name": "Notes",
        "reference": None,
        "checksum": "abc",
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_type", " "),
        ("source_type", "x" * 51),
        ("name", ""),
        ("name", "x" * 256),
        ("checksum", "x" * 65),
    ],
)
def test_source_create_rejects_invalid_lengths(field: str, value: str) -> None:
    data = {"source_type": "note", "name": "Notes", field: value}
    with pytest.raises(ValidationError):
        SourceCreate.model_validate(data)


def test_source_read_serializes_model() -> None:
    now = datetime.now(UTC)
    source = Source(
        id=uuid.uuid4(),
        source_type="note",
        name="Notes",
        reference=None,
        checksum=None,
        created_at=now,
        updated_at=now,
    )
    assert SourceRead.model_validate(source).id == source.id


def test_memory_source_link_create_validation() -> None:
    source_id = uuid.uuid4()
    assert (
        MemorySourceLinkCreate(
            source_id=source_id, source_location=" page 1 "
        ).source_location
        == "page 1"
    )
    assert (
        MemorySourceLinkCreate(source_id=source_id, source_location=" ").source_location
        is None
    )
    with pytest.raises(ValidationError):
        MemorySourceLinkCreate(source_id=source_id, source_location="x" * 501)
