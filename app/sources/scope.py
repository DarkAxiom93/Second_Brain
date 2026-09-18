"""Common fail-closed access guard for capture-bound Source data."""

import uuid
from enum import Enum
from typing import Any

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models.capture_item import CaptureItem
from app.models.source import Source
from app.models.source_chunk import SourceChunk
from app.models.source_document import SourceDocument


class SourceScopeMode(Enum):
    LEGACY_ONLY = "legacy_only"


LEGACY_ONLY = SourceScopeMode.LEGACY_ONLY
AuthoritativeScope = uuid.UUID | None


def source_access_clause(
    scope: AuthoritativeScope | SourceScopeMode | Any,
) -> ColumnElement[bool]:
    """Allow unbound Sources, plus only valid capture bindings in exact scope."""

    binding = select(CaptureItem.id).where(CaptureItem.resulting_source_id == Source.id)
    if scope is LEGACY_ONLY:
        return ~exists(binding)
    scope_match = (
        CaptureItem.project_id.is_(None)
        if scope is None
        else CaptureItem.project_id == scope
    )
    valid_binding = binding.where(
        CaptureItem.state == "processed",
        CaptureItem.processed_at.is_not(None),
        scope_match,
    )
    return or_(~exists(binding), exists(valid_binding))


def get_source_for_scope(
    session: Session,
    source_id: uuid.UUID,
    scope: AuthoritativeScope | SourceScopeMode,
) -> Source | None:
    return session.scalar(
        select(Source).where(Source.id == source_id, source_access_clause(scope))
    )


def get_document_for_scope(
    session: Session,
    document_id: uuid.UUID,
    scope: AuthoritativeScope | SourceScopeMode,
) -> SourceDocument | None:
    return session.scalar(
        select(SourceDocument)
        .join(Source, Source.id == SourceDocument.source_id)
        .where(SourceDocument.id == document_id, source_access_clause(scope))
    )


def get_chunk_for_scope(
    session: Session,
    chunk_id: uuid.UUID,
    scope: AuthoritativeScope | SourceScopeMode,
) -> SourceChunk | None:
    return session.scalar(
        select(SourceChunk)
        .join(SourceDocument, SourceDocument.id == SourceChunk.document_id)
        .join(Source, Source.id == SourceDocument.source_id)
        .where(SourceChunk.id == chunk_id, source_access_clause(scope))
    )
