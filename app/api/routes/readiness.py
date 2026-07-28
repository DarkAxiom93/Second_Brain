"""PostgreSQL readiness endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_session
from app.schemas.readiness import ReadinessResponse

router = APIRouter()


@router.get("/ready", response_model=ReadinessResponse)
def readiness(
    session: Annotated[Session, Depends(get_db_session)],
) -> ReadinessResponse:
    """Report whether PostgreSQL can execute a minimal query."""

    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from None
    return ReadinessResponse(status="ready")
