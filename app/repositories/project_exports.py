"""Read-only, explicitly scoped queries for Project exports."""

from collections.abc import Iterator
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import (
    Memory,
    MemoryEmbedding,
    MemoryExtractionRun,
    MemoryProposal,
    MemorySource,
    Project,
    Source,
    SourceChunk,
    SourceDocument,
)


def get_project(session: Session, project_id: UUID) -> Project | None:
    """Return exactly one requested Project."""

    return session.scalar(select(Project).where(Project.id == project_id))


def _rows(session: Session, statement: Select[Any]) -> Iterator[Any]:
    return iter(session.scalars(statement.execution_options(yield_per=500)))


def memories(session: Session, project_id: UUID) -> Iterator[Memory]:
    return _rows(
        session,
        select(Memory).where(Memory.project_id == project_id).order_by(Memory.id),
    )


def embeddings(session: Session, project_id: UUID) -> Iterator[MemoryEmbedding]:
    return _rows(
        session,
        select(MemoryEmbedding)
        .join(Memory)
        .where(Memory.project_id == project_id)
        .order_by(MemoryEmbedding.id),
    )


def memory_sources(session: Session, project_id: UUID) -> Iterator[MemorySource]:
    return _rows(
        session,
        select(MemorySource)
        .join(Memory)
        .where(Memory.project_id == project_id)
        .order_by(MemorySource.id),
    )


def extraction_runs(
    session: Session, project_id: UUID
) -> Iterator[MemoryExtractionRun]:
    return _rows(
        session,
        select(MemoryExtractionRun)
        .where(MemoryExtractionRun.project_id == project_id)
        .order_by(MemoryExtractionRun.id),
    )


def documents(session: Session, project_id: UUID) -> Iterator[SourceDocument]:
    run_documents = select(MemoryExtractionRun.document_id).where(
        MemoryExtractionRun.project_id == project_id
    )
    return _rows(
        session,
        select(SourceDocument)
        .where(SourceDocument.id.in_(run_documents))
        .order_by(SourceDocument.id),
    )


def chunks(session: Session, project_id: UUID) -> Iterator[SourceChunk]:
    run_documents = select(MemoryExtractionRun.document_id).where(
        MemoryExtractionRun.project_id == project_id
    )
    return _rows(
        session,
        select(SourceChunk)
        .where(SourceChunk.document_id.in_(run_documents))
        .order_by(SourceChunk.id),
    )


def sources(session: Session, project_id: UUID) -> Iterator[Source]:
    linked_sources = (
        select(MemorySource.source_id)
        .join(Memory)
        .where(Memory.project_id == project_id)
    )
    document_sources = (
        select(SourceDocument.source_id)
        .join(MemoryExtractionRun)
        .where(MemoryExtractionRun.project_id == project_id)
    )
    return _rows(
        session,
        select(Source)
        .where(Source.id.in_(linked_sources.union(document_sources)))
        .order_by(Source.id),
    )


def proposals(session: Session, project_id: UUID) -> Iterator[MemoryProposal]:
    target_runs = select(MemoryExtractionRun.id).where(
        MemoryExtractionRun.project_id == project_id
    )
    return _rows(
        session,
        select(MemoryProposal)
        .where(
            MemoryProposal.run_id.in_(target_runs),
            MemoryProposal.project_id == project_id,
        )
        .order_by(MemoryProposal.id),
    )
