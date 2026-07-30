"""Focused unit tests for explicit Memory supersession policy and schemas."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.memory_quality.supersession import (
    SupersessionConflict,
    classify_supersession,
)
from app.models.memory import Memory
from app.schemas.memory import MemorySupersedeRequest, MemorySupersessionRead


def memory(
    *,
    memory_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    status: str = "active",
    supersedes_id: uuid.UUID | None = None,
) -> Memory:
    now = datetime.now(UTC)
    return Memory(
        id=memory_id or uuid.uuid4(),
        project_id=project_id,
        content="fact",
        source=None,
        title=None,
        summary=None,
        memory_type="semantic",
        importance=0.5,
        confidence=1.0,
        status=status,
        event_time=None,
        expires_at=None,
        supersedes_id=supersedes_id,
        created_at=now,
        updated_at=now,
    )


def classify(older: Memory, replacement: Memory, **kwargs: object) -> str:
    return classify_supersession(
        older=older,
        replacement=replacement,
        existing_successors=kwargs.get("successors", []),  # type: ignore[arg-type]
        creates_cycle=bool(kwargs.get("cycle", False)),
    )


def test_request_and_response_validation() -> None:
    replacement_id = uuid.uuid4()
    request = MemorySupersedeRequest(replacement_memory_id=replacement_id)
    assert request.replacement_memory_id == replacement_id
    with pytest.raises(ValidationError):
        MemorySupersedeRequest.model_validate({"replacement_memory_id": "bad"})
    with pytest.raises(ValidationError):
        MemorySupersedeRequest.model_validate(
            {"replacement_memory_id": str(replacement_id), "extra": True}
        )

    older = memory(status="superseded")
    replacement = memory(supersedes_id=older.id)
    response = MemorySupersessionRead(
        supersession_status="unchanged",
        superseded_memory=older,
        replacement_memory=replacement,
    )
    assert response.supersession_status == "unchanged"
    with pytest.raises(ValidationError):
        MemorySupersessionRead(
            supersession_status="repaired",  # type: ignore[arg-type]
            superseded_memory=older,
            replacement_memory=replacement,
        )


@pytest.mark.parametrize("left,right", [(None, uuid.uuid4()), (uuid.uuid4(), None)])
def test_project_scope_comparison_rejects_assigned_unassigned(
    left: uuid.UUID | None, right: uuid.UUID | None
) -> None:
    with pytest.raises(SupersessionConflict, match="project scope mismatch"):
        classify(memory(project_id=left), memory(project_id=right))


def test_same_project_and_same_null_project_are_allowed() -> None:
    project_id = uuid.uuid4()
    assert (
        classify(memory(project_id=project_id), memory(project_id=project_id))
        == "updated"
    )
    assert classify(memory(), memory()) == "updated"


def test_exact_existing_state_is_unchanged() -> None:
    older = memory(status="superseded")
    replacement = memory(supersedes_id=older.id)
    assert classify(older, replacement, successors=[replacement]) == "unchanged"


@pytest.mark.parametrize(
    ("setup", "detail"),
    [
        ("direct_cycle", "would create a cycle"),
        ("indirect_cycle", "would create a cycle"),
        ("replacement_linked", "already has a predecessor"),
        ("older_replaced", "already has a replacement"),
        ("inactive", "not eligible"),
        ("inconsistent_link", "inconsistent existing"),
        ("inconsistent_status", "inconsistent existing"),
    ],
)
def test_conflict_classification(setup: str, detail: str) -> None:
    older = memory()
    replacement = memory()
    successors: list[Memory] = []
    cycle = setup in {"direct_cycle", "indirect_cycle"}
    if setup == "replacement_linked":
        replacement.supersedes_id = uuid.uuid4()
    elif setup == "older_replaced":
        successors = [memory(supersedes_id=older.id)]
    elif setup == "inactive":
        replacement.status = "archived"
    elif setup == "inconsistent_link":
        replacement.supersedes_id = older.id
    elif setup == "inconsistent_status":
        older.status = "superseded"
    with pytest.raises(SupersessionConflict, match=detail):
        classify(older, replacement, successors=successors, cycle=cycle)
