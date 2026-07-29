"""Persistence operations for memories."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.project import Project
from app.schemas.memory import MemoryCreate, MemoryStatus, MemoryType


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
    if project_id is not None:
        statement = statement.where(Memory.project_id == project_id)
    if memory_type is not None:
        statement = statement.where(Memory.memory_type == memory_type)
    if status is not None:
        statement = statement.where(Memory.status == status)
    if importance_min is not None:
        statement = statement.where(Memory.importance >= importance_min)
    if importance_max is not None:
        statement = statement.where(Memory.importance <= importance_max)
    if confidence_min is not None:
        statement = statement.where(Memory.confidence >= confidence_min)
    if confidence_max is not None:
        statement = statement.where(Memory.confidence <= confidence_max)
    if event_time_from is not None:
        statement = statement.where(Memory.event_time >= event_time_from)
    if event_time_to is not None:
        statement = statement.where(Memory.event_time <= event_time_to)
    if created_at_from is not None:
        statement = statement.where(Memory.created_at >= created_at_from)
    if created_at_to is not None:
        statement = statement.where(Memory.created_at <= created_at_to)
    if rank is not None:
        statement = statement.order_by(
            rank.desc(), Memory.created_at.desc(), Memory.id.asc()
        )
    else:
        statement = statement.order_by(Memory.created_at.desc(), Memory.id.asc())
    statement = statement.limit(limit).offset(offset)
    return list(session.scalars(statement).all())


def get_memory(session: Session, memory_id: uuid.UUID) -> Memory | None:
    """Return a memory by identifier, or None when it does not exist."""

    return session.scalar(select(Memory).where(Memory.id == memory_id))
