"""Synchronous, transaction-bounded extraction-run lifecycle."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.extraction.canonical import ValidatedProposal, canonical_input, validate_result
from app.extraction.provider import (
    ChunkSnapshot,
    ExtractionProvider,
    InvalidExtractionResponseError,
    ProviderRequestError,
)
from app.models import (
    MemoryExtractionRun,
    MemoryProposal,
    Project,
    Source,
    SourceChunk,
    SourceDocument,
)


class ExtractionHTTPError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status, self.detail = status, detail


@dataclass(frozen=True)
class GenerationResult:
    run: MemoryExtractionRun
    proposal_count: int
    generation_status: str


def _fail_run(session: Session, run_id: uuid.UUID, code: str) -> None:
    try:
        run = session.scalar(
            select(MemoryExtractionRun)
            .where(MemoryExtractionRun.id == run_id)
            .with_for_update()
        )
        if run is not None and run.run_status == "pending":
            run.run_status, run.error_code, run.completed_at = (
                "failed",
                code,
                datetime.now(UTC),
            )
            session.commit()
    except SQLAlchemyError:
        session.rollback()


def generate(
    session: Session,
    *,
    source_id: uuid.UUID,
    project_id: uuid.UUID | None,
    chunk_start: int,
    chunk_limit: int,
    maximum: int,
    provider: ExtractionProvider | None,
) -> GenerationResult:
    if provider is None:
        raise ExtractionHTTPError(503, "extraction provider unavailable")
    try:
        if session.get(Source, source_id) is None:
            raise ExtractionHTTPError(404, "source not found")
        document = session.scalar(
            select(SourceDocument).where(SourceDocument.source_id == source_id)
        )
        if document is None:
            raise ExtractionHTTPError(404, "document not found")
        if project_id is not None and session.get(Project, project_id) is None:
            raise ExtractionHTTPError(404, "project not found")
        rows = session.scalars(
            select(SourceChunk)
            .where(
                SourceChunk.document_id == document.id,
                SourceChunk.chunk_index >= chunk_start,
            )
            .order_by(SourceChunk.chunk_index, SourceChunk.id)
            .limit(chunk_limit)
        ).all()
        if not rows:
            raise ExtractionHTTPError(422, "no chunks selected")
        chunks = [
            ChunkSnapshot(
                chunk_index=c.chunk_index,
                content=c.content,
                content_hash=c.content_hash,
                char_start=c.char_start,
                char_end=c.char_end,
                locator=c.locator,
            )
            for c in rows
        ]
        try:
            _, input_hash, chunks = canonical_input(
                provider=provider.name,
                model=provider.model,
                prompt_version=provider.prompt_version,
                project_id=project_id,
                max_proposals_per_chunk=maximum,
                chunks=chunks,
            )
        except ValueError:
            raise ExtractionHTTPError(422, "extraction input too large") from None
        identity = (
            MemoryExtractionRun.document_id == document.id,
            MemoryExtractionRun.provider == provider.name,
            MemoryExtractionRun.model == provider.model,
            MemoryExtractionRun.prompt_version == provider.prompt_version,
            MemoryExtractionRun.input_hash == input_hash,
        )
        run = session.scalar(
            select(MemoryExtractionRun).where(*identity).with_for_update()
        )
        if run and run.run_status == "completed":
            count = (
                session.scalar(
                    select(func.count())
                    .select_from(MemoryProposal)
                    .where(MemoryProposal.run_id == run.id)
                )
                or 0
            )
            session.rollback()
            return GenerationResult(run, count, "unchanged")
        if run and run.run_status == "pending":
            session.rollback()
            raise ExtractionHTTPError(409, "extraction already in progress")
        generation_status = "retried" if run else "created"
        now = datetime.now(UTC)
        if run:
            run.run_status, run.error_code, run.started_at, run.completed_at = (
                "pending",
                None,
                now,
                None,
            )
        else:
            run = MemoryExtractionRun(
                document_id=document.id,
                project_id=project_id,
                provider=provider.name,
                model=provider.model,
                prompt_version=provider.prompt_version,
                input_hash=input_hash,
                run_status="pending",
                started_at=now,
            )
            session.add(run)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise ExtractionHTTPError(409, "extraction already in progress") from None
        session.refresh(run)
        run_id = run.id
    except ExtractionHTTPError:
        raise
    except SQLAlchemyError:
        session.rollback()
        raise ExtractionHTTPError(503, "database unavailable") from None
    try:
        result = provider.extract(
            "Produce only evidence-supported proposed Memories.", chunks, maximum
        )
    except ProviderRequestError:
        _fail_run(session, run_id, "provider_failed")
        raise ExtractionHTTPError(502, "extraction provider failed") from None
    except Exception:
        _fail_run(session, run_id, "invalid_provider_response")
        raise ExtractionHTTPError(502, "invalid extraction response") from None
    try:
        proposals = validate_result(result, chunks, project_id, maximum)
    except (InvalidExtractionResponseError, ValueError):
        _fail_run(session, run_id, "invalid_provider_response")
        raise ExtractionHTTPError(502, "invalid extraction response") from None
    try:
        locked = session.scalar(
            select(MemoryExtractionRun)
            .where(MemoryExtractionRun.id == run_id)
            .with_for_update()
        )
        if locked is None or locked.run_status != "pending":
            raise ExtractionHTTPError(409, "extraction already in progress")
        session.execute(delete(MemoryProposal).where(MemoryProposal.run_id == run_id))
        chunk_ids = {row.chunk_index: row.id for row in rows}
        for p in proposals:
            session.add(
                _proposal(run_id, project_id, chunk_ids[p.chunk.chunk_index], p)
            )
        locked.run_status, locked.error_code, locked.completed_at = (
            "completed",
            None,
            datetime.now(UTC),
        )
        session.commit()
        session.refresh(locked)
        return GenerationResult(locked, len(proposals), generation_status)
    except ExtractionHTTPError:
        session.rollback()
        raise
    except SQLAlchemyError:
        session.rollback()
        raise ExtractionHTTPError(503, "database unavailable") from None


def _proposal(
    run_id: uuid.UUID,
    project_id: uuid.UUID | None,
    chunk_id: uuid.UUID,
    p: ValidatedProposal,
) -> MemoryProposal:
    return MemoryProposal(
        run_id=run_id,
        source_chunk_id=chunk_id,
        source_chunk_hash=p.chunk.content_hash,
        project_id=project_id,
        proposal_index=p.proposal_index,
        title=p.title,
        summary=p.summary,
        content=p.content,
        memory_type=p.memory_type,
        importance=p.importance,
        confidence=p.confidence,
        evidence_text=p.evidence_text,
        evidence_char_start=p.evidence_char_start,
        evidence_char_end=p.evidence_char_end,
        source_locator=p.chunk.locator,
        proposal_hash=p.proposal_hash,
        review_status="pending",
    )
