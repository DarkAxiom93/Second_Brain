"""Persistence operations for memories."""

import uuid
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.memory_embedding import MemoryEmbedding
from app.models.project import Project
from app.schemas.memory import MemoryCreate, MemoryStatus, MemoryType


def _apply_structured_filters(
    statement: Select[tuple[Memory]],
    *,
    project_id: uuid.UUID | None,
    memory_type: MemoryType | None,
    status: MemoryStatus | None,
    importance_min: float | None,
    importance_max: float | None,
    confidence_min: float | None,
    confidence_max: float | None,
    event_time_from: datetime | None,
    event_time_to: datetime | None,
    created_at_from: datetime | None,
    created_at_to: datetime | None,
) -> Select[tuple[Memory]]:
    """Apply the canonical Memory structured predicates to a statement."""

    values = (
        (project_id, Memory.project_id, "eq"),
        (memory_type, Memory.memory_type, "eq"),
        (status, Memory.status, "eq"),
        (importance_min, Memory.importance, "ge"),
        (importance_max, Memory.importance, "le"),
        (confidence_min, Memory.confidence, "ge"),
        (confidence_max, Memory.confidence, "le"),
        (event_time_from, Memory.event_time, "ge"),
        (event_time_to, Memory.event_time, "le"),
        (created_at_from, Memory.created_at, "ge"),
        (created_at_to, Memory.created_at, "le"),
    )
    for value, column, operation in values:
        if value is None:
            continue
        if operation == "eq":
            statement = statement.where(column == value)
        elif operation == "ge":
            statement = statement.where(column >= value)
        else:
            statement = statement.where(column <= value)
    return statement


def project_exists(session: Session, project_id: uuid.UUID) -> bool:
    """Return whether the project identifier exists."""

    statement = select(Project.id).where(Project.id == project_id)
    return session.scalar(statement) is not None


def create_memory(session: Session, memory_data: MemoryCreate) -> Memory:
    """Add and flush a Memory without committing its transaction."""

    memory = Memory(**memory_data.model_dump())
    session.add(memory)
    session.flush()
    session.refresh(memory)
    return memory


def list_memories(
    session: Session,
    *,
    project_id: uuid.UUID | None,
    query: str | None = None,
    memory_type: MemoryType | None = None,
    status: MemoryStatus | None = None,
    importance_min: float | None = None,
    importance_max: float | None = None,
    confidence_min: float | None = None,
    confidence_max: float | None = None,
    event_time_from: datetime | None = None,
    event_time_to: datetime | None = None,
    created_at_from: datetime | None = None,
    created_at_to: datetime | None = None,
    limit: int,
    offset: int,
) -> list[Memory]:
    """Return a deterministic, SQL-filtered page of memories."""

    statement = select(Memory)
    rank = None
    if query is not None:
        search_query = func.websearch_to_tsquery("simple", query)
        statement = statement.where(Memory.search_vector.bool_op("@@")(search_query))
        rank = func.ts_rank_cd(Memory.search_vector, search_query)
    statement = _apply_structured_filters(
        statement,
        project_id=project_id,
        memory_type=memory_type,
        status=status,
        importance_min=importance_min,
        importance_max=importance_max,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        event_time_from=event_time_from,
        event_time_to=event_time_to,
        created_at_from=created_at_from,
        created_at_to=created_at_to,
    )
    if rank is not None:
        statement = statement.order_by(
            rank.desc(), Memory.created_at.desc(), Memory.id.asc()
        )
    else:
        statement = statement.order_by(Memory.created_at.desc(), Memory.id.asc())
    statement = statement.limit(limit).offset(offset)
    return list(session.scalars(statement).all())


def search_memories(
    session: Session,
    *,
    query_vector: list[float],
    project_id: uuid.UUID | None = None,
    memory_type: MemoryType | None = None,
    status: MemoryStatus | None = None,
    importance_min: float | None = None,
    importance_max: float | None = None,
    confidence_min: float | None = None,
    confidence_max: float | None = None,
    event_time_from: datetime | None = None,
    event_time_to: datetime | None = None,
    created_at_from: datetime | None = None,
    created_at_to: datetime | None = None,
    limit: int,
    offset: int,
) -> list[Memory]:
    """Return one SQL-ranked page of Memories with stored embeddings."""

    distance = MemoryEmbedding.embedding.cosine_distance(query_vector)
    statement = select(Memory).join(MemoryEmbedding)
    statement = _apply_structured_filters(
        statement,
        project_id=project_id,
        memory_type=memory_type,
        status=status,
        importance_min=importance_min,
        importance_max=importance_max,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        event_time_from=event_time_from,
        event_time_to=event_time_to,
        created_at_from=created_at_from,
        created_at_to=created_at_to,
    )
    statement = statement.order_by(
        distance.asc(), Memory.created_at.desc(), Memory.id.asc()
    )
    return list(session.scalars(statement.offset(offset).limit(limit)).all())


def get_memory(session: Session, memory_id: uuid.UUID) -> Memory | None:
    """Return a memory by identifier, or None when it does not exist."""

    return session.scalar(select(Memory).where(Memory.id == memory_id))
