"""Focused tests for explicit Memory expiration policy and response schema."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.memory_quality.expiration import ExpirationConflict, classify_expiration
from app.models.memory import Memory
from app.schemas.memory import MemoryExpirationRead, MemoryRead


def memory(*, status: str = "active", expires_at: datetime | None = None) -> Memory:
    now = datetime.now(UTC)
    return Memory(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        content="preserved fact",
        source="manual",
        title="Title",
        summary="Summary",
        memory_type="decision",
        importance=0.8,
        confidence=0.7,
        status=status,
        event_time=now - timedelta(days=2),
        expires_at=expires_at,
        supersedes_id=uuid.uuid4(),
        created_at=now - timedelta(days=1),
        updated_at=now,
    )


def test_expired_status_and_response_statuses_validate() -> None:
    row = memory(status="expired", expires_at=datetime.now(UTC))
    assert MemoryRead.model_validate(row).status == "expired"
    for status in ("updated", "unchanged"):
        result = MemoryExpirationRead(expiration_status=status, memory=row)  # type: ignore[arg-type]
        assert result.expiration_status == status
    with pytest.raises(ValidationError):
        MemoryExpirationRead(expiration_status="repaired", memory=row)  # type: ignore[arg-type]


@pytest.mark.parametrize("offset", [None, timedelta(hours=1), timedelta(hours=-1)])
def test_timestamp_selection_rules(offset: timedelta | None) -> None:
    captured = datetime(2026, 7, 30, 12, tzinfo=UTC)
    existing = None if offset is None else captured + offset
    decision = classify_expiration(
        memory=memory(expires_at=existing), captured_at=captured
    )
    assert decision.status == "updated"
    assert decision.expires_at == (
        captured if offset is None or offset > timedelta() else existing
    )
    assert decision.expires_at.tzinfo is UTC


def test_equal_timestamp_is_preserved() -> None:
    captured = datetime(2026, 7, 30, 12, tzinfo=UTC)
    assert (
        classify_expiration(
            memory=memory(expires_at=captured), captured_at=captured
        ).expires_at
        is captured
    )


@pytest.mark.parametrize("status", ["superseded", "invalid", "archived", "deleted"])
def test_ineligible_statuses_conflict(status: str) -> None:
    with pytest.raises(ExpirationConflict, match="not eligible"):
        classify_expiration(memory=memory(status=status), captured_at=datetime.now(UTC))


def test_inconsistent_and_idempotent_expired_states() -> None:
    captured = datetime.now(UTC)
    with pytest.raises(ExpirationConflict, match="state is inconsistent"):
        classify_expiration(memory=memory(status="expired"), captured_at=captured)
    existing = captured - timedelta(days=1)
    decision = classify_expiration(
        memory=memory(status="expired", expires_at=existing), captured_at=captured
    )
    assert decision.status == "unchanged" and decision.expires_at is existing


def test_classification_does_not_mutate_any_field() -> None:
    row = memory(expires_at=None)
    before = dict(row.__dict__)
    classify_expiration(memory=row, captured_at=datetime.now(UTC))
    assert row.__dict__ == before


def test_captured_timestamp_must_be_timezone_aware() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        classify_expiration(memory=memory(), captured_at=datetime(2026, 1, 1))
