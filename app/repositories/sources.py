"""Persistence operations for sources and memory-source links."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.memory_source import MemorySource
from app.models.source import Source
from app.schemas.source import MemorySourceLinkCreate, SourceCreate


@dataclass(frozen=True)
class LinkedSource:
    """A source projected together with its memory-link fields."""

    link_id: uuid.UUID
    memory_id: uuid.UUID
    source_id: uuid.UUID
    source_location: str | None
    linked_at: datetime
    source_type: str
    name: str
    reference: str | None
    checksum: str | None
    source_created_at: datetime
    source_updated_at: datetime


@dataclass(frozen=True)
class LinkedMemory:
    """A memory projected together with its source-link fields."""

    link_id: uuid.UUID
    source_id: uuid.UUID
    memory_id: uuid.UUID
    source_location: str | None
    linked_at: datetime
    project_id: uuid.UUID | None
    content: str
    legacy_source: str | None
    title: str | None
    summary: str | None
    memory_type: str
    importance: float
    confidence: float
    status: str
    event_time: datetime | None
    expires_at: datetime | None
    supersedes_id: uuid.UUID | None
    memory_created_at: datetime
    memory_updated_at: datetime


def create_source(session: Session, source_data: SourceCreate) -> Source:
    """Add and flush a Source without committing."""
    source = Source(**source_data.model_dump())
    session.add(source)
    session.flush()
    session.refresh(source)
    return source


def get_source(session: Session, source_id: uuid.UUID) -> Source | None:
    """Return a source by identifier, or None."""
    return session.scalar(select(Source).where(Source.id == source_id))


def create_memory_source_link(
    session: Session, *, memory_id: uuid.UUID, link_data: MemorySourceLinkCreate
) -> MemorySource:
    """Add and flush a memory-source link without committing."""
    link = MemorySource(memory_id=memory_id, **link_data.model_dump())
    session.add(link)
    session.flush()
    session.refresh(link)
    return link


def memory_source_link_exists(
    session: Session, *, memory_id: uuid.UUID, source_id: uuid.UUID
) -> bool:
    """Return whether the pair is already linked."""
    statement = select(MemorySource.id).where(
        MemorySource.memory_id == memory_id, MemorySource.source_id == source_id
    )
    return session.scalar(statement) is not None


def list_sources_for_memory(
    session: Session, *, memory_id: uuid.UUID, limit: int, offset: int
) -> list[LinkedSource]:
    """Return one SQL-paginated page of Sources linked to a Memory."""
    statement = (
        select(
            MemorySource.id,
            MemorySource.memory_id,
            MemorySource.source_id,
            MemorySource.source_location,
            MemorySource.created_at,
            Source.source_type,
            Source.name,
            Source.reference,
            Source.checksum,
            Source.created_at,
            Source.updated_at,
        )
        .join(Source, Source.id == MemorySource.source_id)
        .where(MemorySource.memory_id == memory_id)
        .order_by(MemorySource.created_at.desc(), MemorySource.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return [LinkedSource(*row) for row in session.execute(statement).all()]


def list_memories_for_source(
    session: Session, *, source_id: uuid.UUID, limit: int, offset: int
) -> list[LinkedMemory]:
    """Return one SQL-paginated page of Memories linked to a Source."""
    statement = (
        select(
            MemorySource.id,
            MemorySource.source_id,
            MemorySource.memory_id,
            MemorySource.source_location,
            MemorySource.created_at,
            Memory.project_id,
            Memory.content,
            Memory.source,
            Memory.title,
            Memory.summary,
            Memory.memory_type,
            Memory.importance,
            Memory.confidence,
            Memory.status,
            Memory.event_time,
            Memory.expires_at,
            Memory.supersedes_id,
            Memory.created_at,
            Memory.updated_at,
        )
        .join(Memory, Memory.id == MemorySource.memory_id)
        .where(MemorySource.source_id == source_id)
        .order_by(MemorySource.created_at.desc(), MemorySource.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return [LinkedMemory(*row) for row in session.execute(statement).all()]
