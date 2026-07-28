"""Source creation endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_session
from app.models.source import Source
from app.repositories import sources as source_repository
from app.schemas.source import SourceCreate, SourceRead

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
