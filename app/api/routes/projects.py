"""Project creation and retrieval endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_session
from app.models.project import Project
from app.repositories import projects as project_repository
from app.schemas.project import ProjectCreate, ProjectRead

router = APIRouter(prefix="/projects", tags=["projects"])


def database_unavailable() -> HTTPException:
    """Build the public database-failure response."""

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="database unavailable",
    )


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    project_data: ProjectCreate,
    session: Annotated[Session, Depends(get_db_session)],
) -> Project:
    """Create a Project in one route-owned transaction."""

    try:
        project = project_repository.create_project(session, project_data)
        session.commit()
        session.refresh(project)
    except SQLAlchemyError:
        session.rollback()
        raise database_unavailable() from None
    return project


@router.get("", response_model=list[ProjectRead])
def list_projects(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Project]:
    """List a validated, deterministic page of Projects."""

    try:
        return project_repository.list_projects(
            session,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError:
        raise database_unavailable() from None


@router.get(
    "/{project_id}",
    response_model=ProjectRead,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Project not found"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database unavailable",
        },
    },
)
def get_project(
    project_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> Project:
    """Retrieve one Project without changing database state."""

    try:
        project = project_repository.get_project(session, project_id)
    except SQLAlchemyError:
        raise database_unavailable() from None
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="project not found",
        )
    return project
