"""Focused exact-dispatch and safe-projection tests for Checkpoint 66."""

import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.agent_runs.executor import _safe_projection
from app.agent_tools import dispatch
from app.agent_tools.dispatch import (
    ToolCallContext,
    ToolControlledFailure,
    ToolInputInvalidError,
    ToolOutputInvalidError,
    ToolUnavailableError,
    dispatch_exact,
    executable_identities,
)

EXPECTED = frozenset(
    {
        ("project.get", 1),
        ("memory.get", 1),
        ("memory.search_explained", 1),
        ("source.get", 1),
        ("source_chunk.get", 1),
    }
)


def _context(project_id: uuid.UUID | None = None) -> ToolCallContext:
    return ToolCallContext(Mock(), project_id)


def test_exact_dispatch_inventory_and_rejections() -> None:
    assert executable_identities() == EXPECTED
    for name, version in (
        ("Project.get", 1),
        ("project.get", 2),
        ("operations.diagnostics", 1),
        ("maintenance.audit", 1),
    ):
        with pytest.raises(ToolUnavailableError):
            dispatch_exact(
                name=name,
                version=version,
                normalized_input={},
                context=_context(),
            )


def test_project_wrapper_enforces_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id = uuid.uuid4()
    project = SimpleNamespace(id=project_id, name="P", description="D")
    monkeypatch.setattr(dispatch.projects, "get_project", lambda *_: project)
    output = dispatch_exact(
        name="project.get",
        version=1,
        normalized_input={"project_id": project_id},
        context=_context(project_id),
    )
    assert output.id == project_id  # type: ignore[attr-defined]
    with pytest.raises(ToolControlledFailure):
        dispatch_exact(
            name="project.get",
            version=1,
            normalized_input={"project_id": project_id},
            context=_context(None),
        )


@pytest.mark.parametrize(
    ("name", "key", "row"),
    [
        (
            "memory.get",
            "memory_id",
            SimpleNamespace(
                id=uuid.uuid4(),
                project_id=None,
                title="T",
                summary="S",
                content="C",
                memory_type="semantic",
                status="active",
            ),
        ),
        (
            "source.get",
            "source_id",
            SimpleNamespace(
                id=uuid.uuid4(), source_type="url", name="S", reference=None
            ),
        ),
        (
            "source_chunk.get",
            "source_chunk_id",
            SimpleNamespace(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_index=0,
                content="C",
                char_start=0,
                char_end=1,
                locator=None,
            ),
        ),
    ],
)
def test_entity_wrappers_validate_outputs(name: str, key: str, row: object) -> None:
    session = Mock()
    session.scalar.return_value = row
    output = dispatch_exact(
        name=name,
        version=1,
        normalized_input={key: row.id},  # type: ignore[attr-defined]
        context=ToolCallContext(session, None),
    )
    assert output.id == row.id  # type: ignore[attr-defined]


def test_search_wrapper_is_provider_free_for_lexical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory_id = uuid.uuid4()
    memory = SimpleNamespace(id=memory_id, title="T", summary="S")
    row = SimpleNamespace(rank=1, memory=memory, lexical_rank=1, semantic_rank=None)
    monkeypatch.setattr(
        dispatch.memories, "search_memories_explained", lambda *_, **__: [row]
    )
    output = dispatch_exact(
        name="memory.search_explained",
        version=1,
        normalized_input={
            "query": "q",
            "mode": "lexical",
            "filters": {},
            "pagination": {"limit": 10, "offset": 0},
        },
        context=_context(None),
    )
    summary, evidence = _safe_projection(output, "memory.search_explained")
    assert summary == "explained search returned 1 result(s)"
    assert evidence == [{"entity_type": "memory", "id": str(memory_id)}]


def test_strict_input_and_output_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id = uuid.uuid4()
    with pytest.raises(ToolInputInvalidError):
        dispatch_exact(
            name="project.get",
            version=1,
            normalized_input={"project_id": project_id, "extra": True},
            context=_context(project_id),
        )
    monkeypatch.setattr(
        dispatch.projects,
        "get_project",
        lambda *_: SimpleNamespace(id=project_id, name="P", description="x" * 2001),
    )
    with pytest.raises(ToolOutputInvalidError):
        dispatch_exact(
            name="project.get",
            version=1,
            normalized_input={"project_id": project_id},
            context=_context(project_id),
        )
