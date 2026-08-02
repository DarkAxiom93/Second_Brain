"""Source creation, retrieval, and existing relationship endpoints."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_session
from app.extraction.dependencies import get_extraction_provider
from app.extraction.provider import ExtractionProvider
from app.extraction.service import ExtractionHTTPError, generate
from app.ingestion.files import (
    DocumentExtractionError,
    DocumentTooLargeError,
    NoExtractableTextError,
    UnsupportedDocumentTypeError,
    assign_page_locators,
    extract_document,
    read_bounded,
)
from app.ingestion.text import chunk_text
from app.models.source import Source
from app.models.source_chunk import SourceChunk
from app.repositories import sources as source_repository
from app.schemas.memory_proposal import (
    MemoryProposalGenerationRead,
    MemoryProposalGenerationRequest,
)
from app.schemas.source import (
    LinkedMemoryRead,
    SourceChunkRead,
    SourceCreate,
    SourceDocumentDetailRead,
    SourceDocumentRead,
    SourceRead,
    SourceTextIngest,
)

router = APIRouter(prefix="/sources", tags=["sources"])
document_router = APIRouter(prefix="/source-documents", tags=["source-documents"])


def database_unavailable() -> HTTPException:
    """Build the established public database-failure response."""
    return HTTPException(status_code=503, detail="database unavailable")


@router.post(
    "/{source_id}/memory-proposals", response_model=MemoryProposalGenerationRead
)
def generate_memory_proposals(
    source_id: uuid.UUID,
    request: MemoryProposalGenerationRequest,
    session: Annotated[Session, Depends(get_db_session)],
    provider: Annotated[ExtractionProvider | None, Depends(get_extraction_provider)],
) -> MemoryProposalGenerationRead:
    """Explicitly generate pending proposals from one bounded chunk batch."""
    try:
        result = generate(
            session,
            source_id=source_id,
            project_id=request.project_id,
            chunk_start=request.chunk_start,
            chunk_limit=request.chunk_limit,
            maximum=request.max_proposals_per_chunk,
            provider=provider,
        )
    except ExtractionHTTPError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from None
    run = result.run
    return MemoryProposalGenerationRead(
        id=run.id,
        document_id=run.document_id,
        project_id=run.project_id,
        provider=run.provider,
        model=run.model,
        prompt_version=run.prompt_version,
        input_hash=run.input_hash,
        run_status="completed",
        error_code=run.error_code,
        started_at=run.started_at,  # type: ignore[arg-type]
        completed_at=run.completed_at,  # type: ignore[arg-type]
        created_at=run.created_at,
        updated_at=run.updated_at,
        proposal_count=result.proposal_count,
        generation_status=result.generation_status,  # type: ignore[arg-type]
    )


def _document_response(
    result: source_repository.DocumentIngestionResult,
) -> SourceDocumentRead:
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
    return _document_response(result)


@router.put("/{source_id}/document/file", response_model=SourceDocumentRead)
async def ingest_source_file(
    source_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
    file: Annotated[UploadFile, File()],
    chunk_size: Annotated[int, Form(ge=1000, le=10000)] = 2000,
    chunk_overlap: Annotated[int, Form(ge=0, le=500)] = 200,
) -> SourceDocumentRead:
    """Extract and store one bounded UTF-8 TXT or text-layer PDF upload."""
    if chunk_overlap >= chunk_size:
        raise HTTPException(status_code=422, detail="invalid chunk settings")
    try:
        if source_repository.get_source(session, source_id) is None:
            raise HTTPException(status_code=404, detail="source not found")
        try:
            data = read_bounded(file.file)
            extracted = extract_document(data, file.filename, file.content_type)
            chunks = chunk_text(extracted.text, chunk_size, chunk_overlap)
            if extracted.page_ranges:
                chunks = assign_page_locators(chunks, extracted.page_ranges)
        except DocumentTooLargeError:
            raise HTTPException(status_code=413, detail="document too large") from None
        except UnsupportedDocumentTypeError:
            raise HTTPException(
                status_code=415, detail="unsupported document type"
            ) from None
        except NoExtractableTextError:
            raise HTTPException(
                status_code=422, detail="document contains no extractable text"
            ) from None
        except (DocumentExtractionError, ValueError):
            raise HTTPException(
                status_code=422, detail="document extraction failed"
            ) from None
        result = source_repository.upsert_document(
            session,
            source_id=source_id,
            normalized_text=extracted.text,
            media_type=extracted.media_type,
            original_filename=extracted.original_filename,
            byte_size=extracted.byte_size,
            chunks=chunks,
            extracted_at=datetime.now(UTC),
        )
        session.commit()
        session.refresh(result.document)
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(status_code=503, detail="database unavailable") from None
    finally:
        await file.close()
    return _document_response(result)


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


@router.get("", response_model=list[SourceRead])
def list_sources(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Source]:
    """List a validated, deterministic page of Sources."""
    try:
        return source_repository.list_sources(session, limit=limit, offset=offset)
    except SQLAlchemyError:
        raise database_unavailable() from None


@router.get(
    "/{source_id}",
    response_model=SourceRead,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Source not found"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Database unavailable"},
    },
)
def get_source(
    source_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> Source:
    """Retrieve one Source without changing database state."""
    try:
        source = source_repository.get_source(session, source_id)
    except SQLAlchemyError:
        raise database_unavailable() from None
    if source is None:
        raise HTTPException(status_code=404, detail="source not found")
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


@router.get("/{source_id}/documents", response_model=list[SourceDocumentDetailRead])
def list_documents_for_source(
    source_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[source_repository.DocumentRead]:
    """List one deterministic page of documents belonging to a Source."""
    try:
        if source_repository.get_source(session, source_id) is None:
            raise HTTPException(status_code=404, detail="source not found")
        return source_repository.list_documents_for_source(
            session, source_id=source_id, limit=limit, offset=offset
        )
    except SQLAlchemyError:
        raise database_unavailable() from None


@document_router.get("/{document_id}", response_model=SourceDocumentDetailRead)
def get_source_document(
    document_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> source_repository.DocumentRead:
    """Retrieve one SourceDocument without changing database state."""
    try:
        document = source_repository.get_document(session, document_id)
    except SQLAlchemyError:
        raise database_unavailable() from None
    if document is None:
        raise HTTPException(status_code=404, detail="source document not found")
    return document


@document_router.get("/{document_id}/chunks", response_model=list[SourceChunkRead])
def list_source_document_chunks(
    document_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SourceChunk]:
    """List one deterministic page of chunks for an existing document."""
    try:
        if source_repository.get_document(session, document_id) is None:
            raise HTTPException(status_code=404, detail="source document not found")
        return source_repository.list_chunks_for_document(
            session, document_id=document_id, limit=limit, offset=offset
        )
    except SQLAlchemyError:
        raise database_unavailable() from None
