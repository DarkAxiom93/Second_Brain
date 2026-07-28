"""Source creation endpoint."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_session
from app.models.source import Source
from app.repositories import sources as source_repository
from app.schemas.source import LinkedMemoryRead, SourceCreate, SourceRead

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(
    source_data: SourceCreate, session: Annotated[Session, Depends(get_db_session)]
) -> Source:
    """Create a Source in one route-owned transaction."""
    try:
        source = source_repository.create_source(session, source_data)
        session.commit()
        session.refresh(source)
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(status_code=503, detail="database unavailable") from None
    return source


@router.get("/{source_id}/memories", response_model=list[LinkedMemoryRead])
def list_memories_for_source(
    source_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[source_repository.LinkedMemory]:
    """List a validated page of Memories linked to one Source."""
    try:
        if source_repository.get_source(session, source_id) is None:
            raise HTTPException(status_code=404, detail="source not found")
        return source_repository.list_memories_for_source(
            session, source_id=source_id, limit=limit, offset=offset
        )
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="database unavailable") from None
