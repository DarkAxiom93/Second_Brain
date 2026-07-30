"""Joined review-queue queries and row-locked proposal transitions."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.memory_extraction_run import MemoryExtractionRun
from app.models.memory_proposal import MemoryProposal
from app.models.source import Source
from app.models.source_document import SourceDocument
from app.schemas.memory_proposal import MemoryProposalFilters


@dataclass(frozen=True)
class ProposalView:
    values: dict[str, Any]

    def __getattr__(self, name: str) -> Any:
        try:
            return self.values[name]
        except KeyError:
            raise AttributeError(name) from None


@dataclass(frozen=True)
class ReviewTransition:
    proposal: ProposalView
    transition_status: Literal["updated", "unchanged"]


class ProposalNotFoundError(Exception):
    pass


class ProposalAlreadyReviewedError(Exception):
    pass


class ExtractionRunNotCompletedError(Exception):
    pass


def _joined_statement() -> Select[tuple[Any, ...]]:
    return (
        select(
            MemoryProposal,
            MemoryExtractionRun,
            SourceDocument.source_id,
            Source.source_type,
            Source.name,
            SourceDocument.original_filename,
        )
        .join(MemoryExtractionRun, MemoryExtractionRun.id == MemoryProposal.run_id)
        .join(SourceDocument, SourceDocument.id == MemoryExtractionRun.document_id)
        .join(Source, Source.id == SourceDocument.source_id)
    )


def _view(row: Any) -> ProposalView:
    proposal, run, source_id, source_type, source_name, original_filename = row
    values = {
        column.name: getattr(proposal, column.name)
        for column in MemoryProposal.__table__.columns
    }
    values.update(
        source_id=source_id,
        document_id=run.document_id,
        source_type=source_type,
        source_name=source_name,
        original_filename=original_filename,
        run_provider=run.provider,
        run_model=run.model,
        run_prompt_version=run.prompt_version,
        run_status=run.run_status,
        source_chunk_available=proposal.source_chunk_id is not None,
    )
    return ProposalView(values)


def list_proposals(
    session: Session, filters: MemoryProposalFilters
) -> list[ProposalView]:
    statement = _joined_statement()
    predicates = []
    if filters.review_status != "all":
        predicates.append(MemoryProposal.review_status == filters.review_status)
    mapping = (
        (filters.run_id, MemoryProposal.run_id),
        (filters.source_id, SourceDocument.source_id),
        (filters.document_id, MemoryExtractionRun.document_id),
        (filters.project_id, MemoryProposal.project_id),
        (filters.memory_type, MemoryProposal.memory_type),
    )
    predicates.extend(column == value for value, column in mapping if value is not None)
    ranges = (
        (filters.importance_min, MemoryProposal.importance, True),
        (filters.importance_max, MemoryProposal.importance, False),
        (filters.confidence_min, MemoryProposal.confidence, True),
        (filters.confidence_max, MemoryProposal.confidence, False),
    )
    for value, column, is_minimum in ranges:
        if value is not None:
            predicates.append(column >= value if is_minimum else column <= value)
    statement = (
        statement.where(*predicates)
        .order_by(MemoryProposal.created_at.asc(), MemoryProposal.id.asc())
        .limit(filters.limit)
        .offset(filters.offset)
    )
    return [_view(row) for row in session.execute(statement).all()]


def get_proposal(session: Session, proposal_id: uuid.UUID) -> ProposalView | None:
    row = session.execute(
        _joined_statement().where(MemoryProposal.id == proposal_id)
    ).one_or_none()
    return None if row is None else _view(row)


def review_proposal(
    session: Session,
    proposal_id: uuid.UUID,
    decision: Literal["approved", "rejected"],
    review_note: str | None,
) -> ReviewTransition:
    locked = session.execute(
        select(MemoryProposal, MemoryExtractionRun)
        .join(MemoryExtractionRun, MemoryExtractionRun.id == MemoryProposal.run_id)
        .where(MemoryProposal.id == proposal_id)
        .with_for_update(of=MemoryProposal)
    ).one_or_none()
    if locked is None:
        raise ProposalNotFoundError
    proposal, run = locked
    if run.run_status != "completed":
        raise ExtractionRunNotCompletedError
    if proposal.review_status == decision:
        transition_status: Literal["updated", "unchanged"] = "unchanged"
    elif proposal.review_status != "pending":
        raise ProposalAlreadyReviewedError
    else:
        proposal.review_status = decision
        proposal.review_note = review_note
        proposal.reviewed_at = datetime.now(UTC)
        session.flush()
        transition_status = "updated"
    detail = get_proposal(session, proposal_id)
    assert detail is not None
    return ReviewTransition(detail, transition_status)
