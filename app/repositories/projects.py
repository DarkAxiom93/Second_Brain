"""Persistence operations for projects."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.schemas.project import ProjectCreate


def create_project(session: Session, project_data: ProjectCreate) -> Project:
    """Add and flush a Project without committing its transaction."""

    project = Project(**project_data.model_dump())
    session.add(project)
    session.flush()
    session.refresh(project)
    return project


def list_projects(
    session: Session,
    *,
    limit: int,
    offset: int,
) -> list[Project]:
    """Return a deterministic page of projects."""

    statement = (
        select(Project)
        .order_by(Project.created_at.desc(), Project.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(statement).all())
