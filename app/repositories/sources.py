"""Persistence operations for sources and memory-source links."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory_source import MemorySource
from app.models.source import Source
from app.schemas.source import MemorySourceLinkCreate, SourceCreate


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
