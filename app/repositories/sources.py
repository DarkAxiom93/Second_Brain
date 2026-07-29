"""Persistence operations for sources and memory-source links."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ingestion.text import TextChunk
from app.models.memory import Memory
from app.models.memory_source import MemorySource
from app.models.source import Source
from app.models.source_chunk import SourceChunk
from app.models.source_document import SourceDocument
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


@dataclass(frozen=True)
class DocumentIngestionResult:
    """A document plus its idempotency outcome and chunk count."""

    document: SourceDocument
    chunk_count: int
    generation_status: Literal["created", "updated", "unchanged"]


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


def upsert_text_document(
    session: Session,
    *,
    source_id: uuid.UUID,
    normalized_text: str,
    original_filename: str | None,
    chunks: list[TextChunk],
    extracted_at: datetime,
) -> DocumentIngestionResult:
    """Create or minimally update one Source document without committing."""
    document = session.scalar(
        select(SourceDocument)
        .where(SourceDocument.source_id == source_id)
        .options(selectinload(SourceDocument.chunks))
    )
    byte_size = len(normalized_text.encode("utf-8"))
    if document is None:
        document = SourceDocument(
            source_id=source_id,
            media_type="text/plain",
            original_filename=original_filename,
            byte_size=byte_size,
            extracted_text=normalized_text,
            ingestion_status="extracted",
            error_code=None,
            extracted_at=extracted_at,
        )
        document.chunks = [SourceChunk(**chunk.__dict__) for chunk in chunks]
        session.add(document)
        session.flush()
        return DocumentIngestionResult(document, len(chunks), "created")

    chunks_identical = len(document.chunks) == len(chunks) and all(
        (
            stored.chunk_index,
            stored.content,
            stored.char_start,
            stored.char_end,
            stored.content_hash,
            stored.locator,
        )
        == (
            generated.chunk_index,
            generated.content,
            generated.char_start,
            generated.char_end,
            generated.content_hash,
            generated.locator,
        )
        for stored, generated in zip(document.chunks, chunks, strict=True)
    )
    metadata_identical = (
        document.media_type == "text/plain"
        and document.original_filename == original_filename
        and document.byte_size == byte_size
        and document.extracted_text == normalized_text
        and document.ingestion_status == "extracted"
        and document.error_code is None
    )
    if metadata_identical and chunks_identical:
        return DocumentIngestionResult(document, len(chunks), "unchanged")

    document.media_type = "text/plain"
    document.original_filename = original_filename
    document.byte_size = byte_size
    document.extracted_text = normalized_text
    document.ingestion_status = "extracted"
    document.error_code = None
    document.extracted_at = extracted_at
    if not chunks_identical:
        document.chunks.clear()
        session.flush()
        document.chunks = [SourceChunk(**chunk.__dict__) for chunk in chunks]
    session.flush()
    return DocumentIngestionResult(document, len(chunks), "updated")


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
