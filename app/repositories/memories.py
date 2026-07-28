"""Persistence operations for memories."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.project import Project
from app.schemas.memory import MemoryCreate


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
    limit: int,
    offset: int,
) -> list[Memory]:
    """Return a deterministic, optionally project-filtered page of memories."""

    statement = select(Memory)
    if project_id is not None:
        statement = statement.where(Memory.project_id == project_id)
    statement = (
        statement.order_by(Memory.created_at.desc(), Memory.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(statement).all())


def get_memory(session: Session, memory_id: uuid.UUID) -> Memory | None:
    """Return a memory by identifier, or None when it does not exist."""

    return session.scalar(select(Memory).where(Memory.id == memory_id))
