"""Memory creation and retrieval endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_session
from app.models.memory import Memory
from app.models.memory_source import MemorySource
from app.repositories import memories as memory_repository
from app.repositories import sources as source_repository
from app.schemas.memory import MemoryCreate, MemoryRead
from app.schemas.source import MemorySourceLinkCreate, MemorySourceRead

router = APIRouter(prefix="/memories", tags=["memories"])


def database_unavailable() -> HTTPException:
    """Build the public database-failure response."""

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="database unavailable",
    )


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
        memory = memory_repository.create_memory(session, memory_data)
        session.commit()
        session.refresh(memory)
    except SQLAlchemyError:
        session.rollback()
        raise database_unavailable() from None
    return memory


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


@router.get("", response_model=list[MemoryRead])
def list_memories(
    session: Annotated[Session, Depends(get_db_session)],
    project_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Memory]:
    """List a validated, deterministic page of Memories."""

    try:
        return memory_repository.list_memories(
            session,
            project_id=project_id,
            limit=limit,
            offset=offset,
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
