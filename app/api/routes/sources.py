"""Source creation endpoint."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_session
from app.ingestion.text import chunk_text
from app.models.source import Source
from app.repositories import sources as source_repository
from app.schemas.source import (
    LinkedMemoryRead,
    SourceCreate,
    SourceDocumentRead,
    SourceRead,
    SourceTextIngest,
)

router = APIRouter(prefix="/sources", tags=["sources"])


@router.put("/{source_id}/document/text", response_model=SourceDocumentRead)
def ingest_source_text(
    source_id: uuid.UUID,
    request: SourceTextIngest,
    session: Annotated[Session, Depends(get_db_session)],
) -> SourceDocumentRead:
    """Store explicit normalized text and its deterministic chunks."""
    try:
        if source_repository.get_source(session, source_id) is None:
            raise HTTPException(status_code=404, detail="source not found")
        chunks = chunk_text(request.text, request.chunk_size, request.chunk_overlap)
        result = source_repository.upsert_text_document(
            session,
            source_id=source_id,
            normalized_text=request.text,
            original_filename=request.original_filename,
            chunks=chunks,
            extracted_at=datetime.now(UTC),
        )
        session.commit()
        session.refresh(result.document)
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(status_code=503, detail="database unavailable") from None
    return SourceDocumentRead(
        id=result.document.id,
        source_id=result.document.source_id,
        media_type=result.document.media_type,
        original_filename=result.document.original_filename,
        byte_size=result.document.byte_size or 0,
        ingestion_status=result.document.ingestion_status,
        error_code=result.document.error_code,
        extracted_at=result.document.extracted_at,  # type: ignore[arg-type]
        created_at=result.document.created_at,
        updated_at=result.document.updated_at,
        chunk_count=result.chunk_count,
        generation_status=result.generation_status,
    )


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
