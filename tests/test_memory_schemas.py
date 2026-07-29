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
        "title": None,
        "summary": None,
        "memory_type": "semantic",
        "importance": 0.5,
        "confidence": 1.0,
        "status": "active",
        "event_time": None,
        "expires_at": None,
        "supersedes_id": None,
    }


@pytest.mark.parametrize(
    "memory_type",
    [
        "working",
        "episodic",
        "semantic",
        "decision",
        "procedural",
        "preference",
        "temporary",
    ],
)
def test_memory_create_accepts_every_memory_type(memory_type: str) -> None:
    assert (
        MemoryCreate(content="fact", memory_type=memory_type).memory_type == memory_type
    )


@pytest.mark.parametrize("status", ["active", "superseded", "invalid", "archived"])
def test_memory_create_accepts_every_status(status: str) -> None:
    assert MemoryCreate(content="fact", status=status).status == status


@pytest.mark.parametrize("field", ["memory_type", "status"])
def test_memory_create_rejects_invalid_literal(field: str) -> None:
    with pytest.raises(ValidationError):
        MemoryCreate(content="fact", **{field: "unknown"})


@pytest.mark.parametrize("field", ["importance", "confidence"])
@pytest.mark.parametrize("value", [0.0, 1.0])
def test_memory_create_accepts_score_boundaries(field: str, value: float) -> None:
    assert getattr(MemoryCreate(content="fact", **{field: value}), field) == value


@pytest.mark.parametrize("field", ["importance", "confidence"])
@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_memory_create_rejects_scores_outside_range(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        MemoryCreate(content="fact", **{field: value})


def test_memory_create_trims_optional_text_and_normalizes_blank_text() -> None:
    assert (
        MemoryCreate(content="fact", title="  T  ", summary="  S  ").model_dump()[
            "title"
        ]
        == "T"
    )
    blank = MemoryCreate(content="fact", title="  ", summary="\t")
    assert blank.title is blank.summary is None


def test_memory_create_rejects_title_over_255_characters_after_trimming() -> None:
    with pytest.raises(ValidationError):
        MemoryCreate(content="fact", title="x" * 256)


@pytest.mark.parametrize("field", ["event_time", "expires_at"])
def test_memory_create_rejects_naive_datetime(field: str) -> None:
    with pytest.raises(ValidationError):
        MemoryCreate(content="fact", **{field: datetime(2026, 1, 1)})


def test_memory_create_accepts_timezone_aware_datetimes() -> None:
    timestamp = datetime.now(UTC)
    result = MemoryCreate(content="fact", event_time=timestamp, expires_at=timestamp)
    assert result.event_time == result.expires_at == timestamp


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

    with pytest.raises(ValidationError):
        MemoryCreate(content="fact", search_vector="client supplied")


def test_memory_read_does_not_expose_search_vector() -> None:
    assert "search_vector" not in MemoryRead.model_fields


def test_memory_read_serializes_attribute_object() -> None:
    memory_id = uuid.uuid4()
    timestamp = datetime.now(UTC)
    result = MemoryRead.model_validate(
        SimpleNamespace(
            id=memory_id,
            project_id=None,
            content="fact",
            source=None,
            title="Title",
            summary="Summary",
            memory_type="decision",
            importance=0.8,
            confidence=0.9,
            status="active",
            event_time=timestamp,
            expires_at=timestamp,
            supersedes_id=None,
            created_at=timestamp,
            updated_at=timestamp,
        )
    )
    assert result.model_dump() == {
        "id": memory_id,
        "project_id": None,
        "content": "fact",
        "source": None,
        "title": "Title",
        "summary": "Summary",
        "memory_type": "decision",
        "importance": 0.8,
        "confidence": 0.9,
        "status": "active",
        "event_time": timestamp,
        "expires_at": timestamp,
        "supersedes_id": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
