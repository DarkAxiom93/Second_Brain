"""Pure proposal-definition proofs for Checkpoint 68."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.agent_runs import approvals
from app.models.memory import Memory


def _memory() -> Memory:
    now = datetime(2026, 1, 2, tzinfo=UTC)
    return Memory(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        project_id=None,
        content="Original",
        source=None,
        title="Title",
        summary=None,
        memory_type="semantic",
        importance=0.5,
        confidence=1.0,
        status="active",
        event_time=None,
        expires_at=None,
        supersedes_id=None,
        created_at=now,
        updated_at=now,
    )


def test_memory_update_is_strict_canonical_and_rejects_noop() -> None:
    target = _memory()
    assert approvals.normalize_memory_update(
        {"title": "  Revised  ", "importance": 0.75}, target=target
    ) == {"importance": 0.75, "title": "Revised"}
    with pytest.raises(approvals.InvalidProposalError):
        approvals.normalize_memory_update({"invented": True}, target=target)
    with pytest.raises(approvals.InvalidProposalError):
        approvals.normalize_memory_update({"title": "Title"}, target=target)
    with pytest.raises(approvals.InvalidProposalError):
        approvals.normalize_memory_update({}, target=target)


def test_version_and_proposal_hash_are_deterministic_and_target_bound() -> None:
    target = _memory()
    version = approvals.target_version(target)
    first = approvals.proposal_hash(
        target_id=target.id,
        version=version,
        normalized_input={"title": "Revised", "importance": 0.75},
    )
    second = approvals.proposal_hash(
        target_id=target.id,
        version=version,
        normalized_input={"importance": 0.75, "title": "Revised"},
    )
    assert first == second
    assert len(first) == len(version) == 64
    assert (
        approvals.proposal_hash(
            target_id=target.id,
            version=version,
            normalized_input={"title": "Different"},
        )
        != first
    )
    assert (
        approvals.proposal_hash(
            target_id=target.id,
            version="f" * 64,
            normalized_input={"importance": 0.75, "title": "Revised"},
        )
        != first
    )
    target.content = "Changed"
    assert approvals.target_version(target) != version


def test_every_mutable_memory_field_changes_target_version() -> None:
    target = _memory()
    baseline = approvals.target_version(target)
    mutations = {
        "project_id": uuid.uuid4(),
        "content": "Changed",
        "source": "manual",
        "title": "Changed",
        "summary": "Changed",
        "memory_type": "working",
        "importance": 0.75,
        "confidence": 0.25,
        "status": "archived",
        "event_time": datetime(2026, 1, 3, tzinfo=UTC),
        "expires_at": datetime(2026, 1, 4, tzinfo=UTC),
        "supersedes_id": uuid.uuid4(),
        "updated_at": target.updated_at + timedelta(seconds=1),
    }
    for field, value in mutations.items():
        original = getattr(target, field)
        setattr(target, field, value)
        assert approvals.target_version(target) != baseline, field
        setattr(target, field, original)
        assert approvals.target_version(target) == baseline, field


def test_preview_is_server_owned_bounded_and_content_free() -> None:
    normalized = {f"field_{index:04d}": "secret-content" for index in range(500)}
    preview = approvals._preview(normalized)
    assert len(preview) <= 2000
    assert "secret-content" not in preview


def test_evidence_is_allowlisted_deduplicated_and_bounded() -> None:
    references = [{"entity_type": "memory", "id": str(uuid.uuid4())} for _ in range(25)]
    references.extend(
        [
            {"entity_type": "secret", "id": str(uuid.uuid4())},
            {"entity_type": "memory", "id": "not-a-uuid"},
        ]
    )
    result = approvals._safe_evidence(references)
    assert len(result) == approvals.MAX_EVIDENCE
    assert all(set(item) == {"entity_type", "id"} for item in result)
