"""Exact application-owned dispatch for the five executable read Tools."""

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_tools.registry import AGENT_TOOL_REGISTRY, ToolDefinition
from app.agent_tools.schemas import MemorySearchExplainedInput
from app.embeddings import EmbeddingProvider
from app.embeddings.openai_provider import validate_embedding
from app.models.memory import Memory
from app.models.memory_source import MemorySource
from app.models.source import Source
from app.models.source_chunk import SourceChunk
from app.models.source_document import SourceDocument
from app.repositories import memories, projects


class ToolUnavailableError(Exception):
    code = "tool_unavailable"


class ToolInputInvalidError(Exception):
    code = "tool_input_invalid"


class ToolOutputInvalidError(Exception):
    code = "tool_output_invalid"


class ToolControlledFailure(Exception):
    code = "tool_controlled_failure"


@dataclass(frozen=True, slots=True)
class ToolCallContext:
    session: Session
    project_scope: uuid.UUID | None
    embedding_provider: EmbeddingProvider | None = None


Handler = Callable[[ToolCallContext, BaseModel], object]


def _scope_clause(project_scope: uuid.UUID | None) -> Any:
    return (
        Memory.project_id.is_(None)
        if project_scope is None
        else Memory.project_id == project_scope
    )


def _project_get(context: ToolCallContext, value: BaseModel) -> dict[str, object]:
    if context.project_scope is None:
        raise ToolControlledFailure
    project_id = value.project_id  # type: ignore[attr-defined]
    if project_id != context.project_scope:
        raise ToolControlledFailure
    project = projects.get_project(context.session, project_id)
    if project is None:
        raise ToolControlledFailure
    return {"id": project.id, "name": project.name, "description": project.description}


def _memory_get(context: ToolCallContext, value: BaseModel) -> dict[str, object]:
    memory = context.session.scalar(
        select(Memory).where(
            Memory.id == value.memory_id,  # type: ignore[attr-defined]
            _scope_clause(context.project_scope),
        )
    )
    if memory is None:
        raise ToolControlledFailure
    return {
        "id": memory.id,
        "project_id": memory.project_id,
        "title": memory.title,
        "summary": memory.summary,
        "content": memory.content,
        "memory_type": memory.memory_type,
        "status": memory.status,
    }


def _scoped_source_statement(project_scope: uuid.UUID | None) -> Any:
    return (
        select(Source)
        .join(MemorySource, MemorySource.source_id == Source.id)
        .join(Memory, Memory.id == MemorySource.memory_id)
        .where(_scope_clause(project_scope))
        .distinct()
    )


def _source_get(context: ToolCallContext, value: BaseModel) -> dict[str, object]:
    source = context.session.scalar(
        _scoped_source_statement(context.project_scope).where(
            Source.id == value.source_id  # type: ignore[attr-defined]
        )
    )
    if source is None:
        raise ToolControlledFailure
    return {
        "id": source.id,
        "source_type": source.source_type,
        "name": source.name,
        "reference": source.reference,
    }


def _source_chunk_get(context: ToolCallContext, value: BaseModel) -> dict[str, object]:
    chunk = context.session.scalar(
        select(SourceChunk)
        .join(SourceDocument, SourceDocument.id == SourceChunk.document_id)
        .join(Source, Source.id == SourceDocument.source_id)
        .join(MemorySource, MemorySource.source_id == Source.id)
        .join(Memory, Memory.id == MemorySource.memory_id)
        .where(
            SourceChunk.id == value.source_chunk_id,  # type: ignore[attr-defined]
            _scope_clause(context.project_scope),
        )
        .distinct()
    )
    if chunk is None:
        raise ToolControlledFailure
    return {
        "id": chunk.id,
        "document_id": chunk.document_id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "locator": chunk.locator,
    }


def _search_explained(context: ToolCallContext, value: BaseModel) -> dict[str, object]:
    assert isinstance(value, MemorySearchExplainedInput)
    mode = value.mode
    query = value.query
    query_vector = None
    if mode in {"semantic", "hybrid"}:
        if context.embedding_provider is None:
            raise ToolControlledFailure
        query_vector = validate_embedding(
            context.embedding_provider.embed(query),
            1536,
        )
    rows = memories.search_memories_explained(
        context.session,
        query=query,
        mode=mode,
        query_vector=query_vector,
        project_id=context.project_scope,
        unassigned_only=context.project_scope is None,
        **value.filters.model_dump(),
        **value.pagination.model_dump(),
    )
    results: list[dict[str, object]] = []
    for row in rows:
        matched_by: list[str] = []
        if row.lexical_rank is not None:
            matched_by.append("lexical")
        if row.semantic_rank is not None:
            matched_by.append("semantic")
        results.append(
            {
                "rank": row.rank,
                "memory_id": row.memory.id,
                "title": row.memory.title,
                "summary": row.memory.summary,
                "mode": mode,
                "matched_by": tuple(matched_by),
            }
        )
    return {"results": tuple(results)}


_HANDLERS: Mapping[tuple[str, int], Handler] = MappingProxyType(
    {
        ("project.get", 1): _project_get,
        ("memory.get", 1): _memory_get,
        ("memory.search_explained", 1): _search_explained,
        ("source.get", 1): _source_get,
        ("source_chunk.get", 1): _source_chunk_get,
    }
)


def dispatch_exact(
    *,
    name: str,
    version: int,
    normalized_input: object,
    context: ToolCallContext,
) -> BaseModel:
    """Validate input, invoke one exact handler, and validate exact output."""

    definition: ToolDefinition | None = AGENT_TOOL_REGISTRY.get_exact(name, version)
    handler = _HANDLERS.get((name, version))
    if definition is None or handler is None:
        raise ToolUnavailableError
    try:
        validated_input = definition.input_schema.model_validate(
            normalized_input, strict=True
        )
    except (ValidationError, TypeError, ValueError):
        raise ToolInputInvalidError from None
    result = handler(context, validated_input)
    try:
        return definition.output_schema.model_validate(result, strict=True)
    except (ValidationError, TypeError, ValueError):
        raise ToolOutputInvalidError from None


def executable_identities() -> frozenset[tuple[str, int]]:
    return frozenset(_HANDLERS)
