"""Explicit, row-locked promotion of approved Memory proposals."""

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.memory_extraction_run import MemoryExtractionRun
from app.models.memory_proposal import MemoryProposal
from app.models.memory_source import MemorySource
from app.models.source import Source
from app.models.source_document import SourceDocument


@dataclass(frozen=True)
class PromotionResult:
    proposal_id: uuid.UUID
    promotion_status: Literal["created", "unchanged"]
    memory: Memory


class ProposalNotFoundError(Exception):
    pass


class ProposalNotApprovedError(Exception):
    pass


class ExtractionRunNotCompletedError(Exception):
    pass


def promote_proposal(session: Session, proposal_id: uuid.UUID) -> PromotionResult:
    """Promote one eligible proposal inside the caller-owned transaction."""

    row = session.execute(
        select(
            MemoryProposal,
            MemoryExtractionRun.run_status,
            Source.id,
            Source.name,
            Source.reference,
        )
        .join(MemoryExtractionRun, MemoryExtractionRun.id == MemoryProposal.run_id)
        .join(SourceDocument, SourceDocument.id == MemoryExtractionRun.document_id)
        .join(Source, Source.id == SourceDocument.source_id)
        .where(MemoryProposal.id == proposal_id)
        .with_for_update(of=MemoryProposal)
    ).one_or_none()
    if row is None:
        raise ProposalNotFoundError

    proposal, run_status, source_id, source_name, source_reference = row
    if proposal.memory_id is not None:
        memory = session.get(Memory, proposal.memory_id)
        if memory is not None:
            return PromotionResult(proposal.id, "unchanged", memory)
    if proposal.review_status != "approved":
        raise ProposalNotApprovedError
    if run_status != "completed":
        raise ExtractionRunNotCompletedError

    reference = source_reference.strip() if source_reference else ""
    memory = Memory(
        project_id=proposal.project_id,
        title=proposal.title,
        summary=proposal.summary,
        content=proposal.content,
        source=reference or source_name,
        memory_type=proposal.memory_type,
        importance=proposal.importance,
        confidence=proposal.confidence,
        status="active",
        event_time=None,
        expires_at=None,
        supersedes_id=None,
    )
    session.add(memory)
    session.flush()
    locator = proposal.source_locator.strip() if proposal.source_locator else ""
    session.add(
        MemorySource(
            memory_id=memory.id,
            source_id=source_id,
            source_location=locator
            or f"chars {proposal.evidence_char_start}-{proposal.evidence_char_end}",
        )
    )
    proposal.memory_id = memory.id
    session.flush()
    return PromotionResult(proposal.id, "created", memory)
