"""Memory creation and retrieval endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_session
from app.embeddings import (
    EmbeddingProvider,
    InvalidEmbeddingResponseError,
    ProviderRequestError,
    ProviderUnavailableError,
    get_embedding_provider,
)
from app.embeddings.openai_provider import validate_embedding
from app.models.memory import Memory
from app.models.memory_source import MemorySource
from app.repositories import memories as memory_repository
from app.repositories import memory_embeddings as embedding_repository
from app.repositories import sources as source_repository
from app.schemas.memory import (
    MemoryCreate,
    MemoryFilters,
    MemoryRead,
    MemorySearchRequest,
)
from app.schemas.memory_embedding import MemoryEmbeddingRead
from app.schemas.source import (
    LinkedSourceRead,
    MemorySourceLinkCreate,
    MemorySourceRead,
)

router = APIRouter(prefix="/memories", tags=["memories"])


def provider_dependency() -> EmbeddingProvider:
    """Resolve provider while translating unavailable configuration safely."""

    try:
        return get_embedding_provider()
    except ProviderUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="embedding provider unavailable",
        ) from None


def database_unavailable() -> HTTPException:
    """Build the public database-failure response."""

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="database unavailable",
    )


@router.post("/search", response_model=list[MemoryRead])
def search_memories(
    request: MemorySearchRequest,
    session: Annotated[Session, Depends(get_db_session)],
    provider: Annotated[EmbeddingProvider, Depends(provider_dependency)],
) -> list[Memory]:
    """Search embedded Memories by cosine distance and structured filters."""

    try:
        query_vector = validate_embedding(provider.embed(request.query), 1536)
    except InvalidEmbeddingResponseError:
        raise HTTPException(
            status_code=502, detail="invalid embedding response"
        ) from None
    except ProviderRequestError:
        raise HTTPException(
            status_code=502, detail="embedding provider failed"
        ) from None
    try:
        return memory_repository.search_memories(
            session,
            query_vector=query_vector,
            **request.filters.model_dump(),
            **request.pagination.model_dump(),
        )
    except SQLAlchemyError:
        raise database_unavailable() from None


@router.post("", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
def create_memory(
    memory_data: MemoryCreate,
    session: Annotated[Session, Depends(get_db_session)],
) -> Memory:
    """Create a Memory in one route-owned transaction."""

    try:
        if memory_data.project_id is not None and not memory_repository.project_exists(
            session, memory_data.project_id
        ):
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="project not found",
            )
        if (
            memory_data.supersedes_id is not None
            and memory_repository.get_memory(session, memory_data.supersedes_id) is None
        ):
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="superseded memory not found",
            )
        memory = memory_repository.create_memory(session, memory_data)
        session.commit()
        session.refresh(memory)
    except SQLAlchemyError:
        session.rollback()
        raise database_unavailable() from None
    return memory


@router.post(
    "/{memory_id}/embedding",
    response_model=MemoryEmbeddingRead,
    status_code=status.HTTP_200_OK,
)
def generate_memory_embedding(
    memory_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
    provider: Annotated[EmbeddingProvider, Depends(provider_dependency)],
) -> MemoryEmbeddingRead:
    """Explicitly create or idempotently update one Memory embedding."""

    try:
        memory = memory_repository.get_memory(session, memory_id)
        if memory is None:
            session.rollback()
            raise HTTPException(status_code=404, detail="memory not found")
        result = embedding_repository.generate_memory_embedding(
            session, memory, provider
        )
        session.commit()
    except InvalidEmbeddingResponseError:
        session.rollback()
        raise HTTPException(
            status_code=502, detail="invalid embedding response"
        ) from None
    except ProviderRequestError:
        session.rollback()
        raise HTTPException(
            status_code=502, detail="embedding provider failed"
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise database_unavailable() from None
    row = result.embedding
    return MemoryEmbeddingRead(
        id=row.id,
        memory_id=row.memory_id,
        provider=row.provider,
        model=row.model,
        dimensions=row.dimensions,
        input_hash=row.input_hash,
        embedded_at=row.embedded_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        generation_status=result.generation_status,
    )


@router.post(
    "/{memory_id}/sources",
    response_model=MemorySourceRead,
    status_code=status.HTTP_201_CREATED,
)
def link_source_to_memory(
    memory_id: uuid.UUID,
    link_data: MemorySourceLinkCreate,
    session: Annotated[Session, Depends(get_db_session)],
) -> MemorySource:
    """Link an existing Source to an existing Memory."""
    try:
        if memory_repository.get_memory(session, memory_id) is None:
            session.rollback()
            raise HTTPException(status_code=404, detail="memory not found")
        if source_repository.get_source(session, link_data.source_id) is None:
            session.rollback()
            raise HTTPException(status_code=404, detail="source not found")
        if source_repository.memory_source_link_exists(
            session, memory_id=memory_id, source_id=link_data.source_id
        ):
            session.rollback()
            raise HTTPException(
                status_code=409, detail="source already linked to memory"
            )
        link = source_repository.create_memory_source_link(
            session, memory_id=memory_id, link_data=link_data
        )
        session.commit()
        session.refresh(link)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="source already linked to memory"
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise database_unavailable() from None
    return link


@router.get("/{memory_id}/sources", response_model=list[LinkedSourceRead])
def list_sources_for_memory(
    memory_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[source_repository.LinkedSource]:
    """List a validated page of Sources linked to one Memory."""
    try:
        if memory_repository.get_memory(session, memory_id) is None:
            raise HTTPException(status_code=404, detail="memory not found")
        return source_repository.list_sources_for_memory(
            session, memory_id=memory_id, limit=limit, offset=offset
        )
    except SQLAlchemyError:
        raise database_unavailable() from None


@router.get("", response_model=list[MemoryRead])
def list_memories(
    session: Annotated[Session, Depends(get_db_session)],
    filters: Annotated[MemoryFilters, Query()],
) -> list[Memory]:
    """List a validated, deterministic page of Memories."""

    try:
        return memory_repository.list_memories(
            session,
            **filters.model_dump(),
        )
    except SQLAlchemyError:
        raise database_unavailable() from None


@router.get("/{memory_id}", response_model=MemoryRead)
def get_memory(
    memory_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> Memory:
    """Return one Memory by UUID."""

    try:
        memory = memory_repository.get_memory(session, memory_id)
    except SQLAlchemyError:
        raise database_unavailable() from None
    if memory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="memory not found",
        )
    return memory
