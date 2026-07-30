"""Public human-review queue for generated Memory proposals."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_session
from app.repositories import memory_proposal_promotions as promotion_repository
from app.repositories import memory_proposals as repository
from app.schemas.memory import MemoryRead
from app.schemas.memory_proposal import (
    ApproveMemoryProposal,
    MemoryProposalDetail,
    MemoryProposalFilters,
    MemoryProposalListItem,
    MemoryProposalPromotionResult,
    MemoryProposalReviewResult,
    RejectMemoryProposal,
)

router = APIRouter(prefix="/memory-proposals", tags=["memory-proposals"])


def database_unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="database unavailable")


@router.get("", response_model=list[MemoryProposalListItem])
def list_memory_proposals(
    session: Annotated[Session, Depends(get_db_session)],
    filters: Annotated[MemoryProposalFilters, Query()],
) -> list[repository.ProposalView]:
    try:
        return repository.list_proposals(session, filters)
    except SQLAlchemyError:
        raise database_unavailable() from None


@router.get("/{proposal_id}", response_model=MemoryProposalDetail)
def get_memory_proposal(
    proposal_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> repository.ProposalView:
    try:
        proposal = repository.get_proposal(session, proposal_id)
    except SQLAlchemyError:
        raise database_unavailable() from None
    if proposal is None:
        raise HTTPException(status_code=404, detail="memory proposal not found")
    return proposal


def _review(
    proposal_id: uuid.UUID,
    decision: Literal["approved", "rejected"],
    review_note: str | None,
    session: Session,
) -> MemoryProposalReviewResult:
    try:
        result = repository.review_proposal(session, proposal_id, decision, review_note)
        session.commit()
    except repository.ProposalNotFoundError:
        raise HTTPException(
            status_code=404, detail="memory proposal not found"
        ) from None
    except repository.ProposalAlreadyReviewedError:
        raise HTTPException(
            status_code=409, detail="memory proposal already reviewed"
        ) from None
    except repository.ExtractionRunNotCompletedError:
        raise HTTPException(
            status_code=409, detail="extraction run not completed"
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise database_unavailable() from None
    return MemoryProposalReviewResult(
        **result.proposal.values, transition_status=result.transition_status
    )


@router.post("/{proposal_id}/approve", response_model=MemoryProposalReviewResult)
def approve_memory_proposal(
    proposal_id: uuid.UUID,
    request: ApproveMemoryProposal,
    session: Annotated[Session, Depends(get_db_session)],
) -> MemoryProposalReviewResult:
    return _review(proposal_id, "approved", request.review_note, session)


@router.post("/{proposal_id}/reject", response_model=MemoryProposalReviewResult)
def reject_memory_proposal(
    proposal_id: uuid.UUID,
    request: RejectMemoryProposal,
    session: Annotated[Session, Depends(get_db_session)],
) -> MemoryProposalReviewResult:
    return _review(proposal_id, "rejected", request.review_note, session)


@router.post("/{proposal_id}/promote", response_model=MemoryProposalPromotionResult)
def promote_memory_proposal(
    proposal_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> MemoryProposalPromotionResult:
    try:
        result = promotion_repository.promote_proposal(session, proposal_id)
        session.commit()
    except promotion_repository.ProposalNotFoundError:
        raise HTTPException(
            status_code=404, detail="memory proposal not found"
        ) from None
    except promotion_repository.ProposalNotApprovedError:
        raise HTTPException(
            status_code=409, detail="memory proposal not approved"
        ) from None
    except promotion_repository.ExtractionRunNotCompletedError:
        raise HTTPException(
            status_code=409, detail="extraction run not completed"
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise database_unavailable() from None
    return MemoryProposalPromotionResult(
        proposal_id=result.proposal_id,
        promotion_status=result.promotion_status,
        memory=MemoryRead.model_validate(result.memory),
    )
