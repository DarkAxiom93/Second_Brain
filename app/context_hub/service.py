"""PostgreSQL-only, zero-authority federation over existing context records."""

from __future__ import annotations

import uuid

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.sql.elements import ColumnElement

from app.calendar import query as calendar_query
from app.connectors import query as github_query
from app.context_hub.models import (
    FAMILY_ORDER,
    KIND_FAMILY,
    MAX_FAMILY_WORK,
    MAX_TEXT_CHARACTERS,
    MAX_TITLE_CHARACTERS,
    STATE_FAMILIES,
    TRUST_FAMILIES,
    CalendarPosition,
    CalendarProvenance,
    ContextFamily,
    ContextFamilyResult,
    ContextHubQuery,
    ContextHubResult,
    ContextItem,
    ContextKind,
    ContextProvenance,
    ContextScope,
    ContextState,
    GitHubPosition,
    GitHubProvenance,
    LocalSourcePosition,
    LocalSourceProvenance,
    TrustLabel,
)
from app.models.calendar import (
    CalendarAccountRevision,
    CalendarEventObservation,
    CalendarEventRevision,
    CalendarSyncRun,
)
from app.models.connector import ConnectorAccount, ExternalItem
from app.models.memory import Memory
from app.models.memory_source import MemorySource
from app.models.project import Project
from app.models.source import Source
from app.models.source_chunk import SourceChunk
from app.models.source_document import SourceDocument
from app.schemas.connector import NumberedExternalContent, RepositoryExternalContent


class ContextNotFoundError(Exception):
    """The exact scoped authoritative record cannot be reopened."""


def _scope_clause(
    column: InstrumentedAttribute[uuid.UUID | None], scope: ContextScope
) -> ColumnElement[bool]:
    return column.is_(None) if scope.unassigned else column == scope.project_id


def _require_scope(session: Session, scope: ContextScope) -> None:
    if scope.project_id is not None and session.get(Project, scope.project_id) is None:
        raise ContextNotFoundError


def _bounded(value: str | None, limit: int) -> str:
    return (value or "")[:limit]


def _family_enabled(request: ContextHubQuery, family: ContextFamily) -> bool:
    if family not in request.families:
        return False
    if request.kinds and not any(KIND_FAMILY[kind] == family for kind in request.kinds):
        return False
    if request.trust and not any(
        family in TRUST_FAMILIES[value] for value in request.trust
    ):
        return False
    return not request.states or any(
        family in STATE_FAMILIES[value] for value in request.states
    )


def _local_items(session: Session, request: ContextHubQuery) -> list[ContextItem]:
    if request.states and ContextState.EXTRACTED not in request.states:
        return []
    statement = (
        select(Source, SourceDocument, SourceChunk)
        .join(SourceDocument, SourceDocument.source_id == Source.id)
        .join(SourceChunk, SourceChunk.document_id == SourceDocument.id)
        .join(MemorySource, MemorySource.source_id == Source.id)
        .join(Memory, Memory.id == MemorySource.memory_id)
        .where(
            SourceDocument.ingestion_status == "extracted",
            _scope_clause(Memory.project_id, request.scope),
        )
        .distinct()
    )
    if request.query:
        pattern = f"%{request.query}%"
        statement = statement.where(
            or_(
                Source.name.ilike(pattern),
                Source.reference.ilike(pattern),
                SourceChunk.content.ilike(pattern),
            )
        )
    rows = session.execute(
        statement.order_by(
            Source.created_at.desc(),
            Source.id.asc(),
            SourceChunk.chunk_index.asc(),
            SourceChunk.id.asc(),
        ).limit(request.page_size + 1)
    ).all()
    return [
        ContextItem(
            family=ContextFamily.LOCAL_SOURCE,
            kind=ContextKind.SOURCE_CHUNK,
            scope=request.scope,
            trust=TrustLabel.LOCAL_AUDITED,
            state=ContextState.EXTRACTED,
            title=_bounded(source.name, MAX_TITLE_CHARACTERS),
            text=_bounded(chunk.content, MAX_TEXT_CHARACTERS),
            provenance=LocalSourceProvenance(
                source_id=source.id,
                document_id=document.id,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                content_hash=chunk.content_hash,
            ),
            position=LocalSourcePosition(
                source_created_at=source.created_at,
                source_id=source.id,
                chunk_index=chunk.chunk_index,
                chunk_id=chunk.id,
            ),
        )
        for source, document, chunk in rows[: request.page_size]
    ]


def _github_latest(request: ContextHubQuery) -> Select[tuple[ExternalItem]]:
    latest = (
        select(
            ExternalItem.account_id,
            ExternalItem.external_resource_id,
            ExternalItem.external_item_id,
            func.max(ExternalItem.application_revision).label("revision"),
        )
        .group_by(
            ExternalItem.account_id,
            ExternalItem.external_resource_id,
            ExternalItem.external_item_id,
        )
        .subquery()
    )
    statement = (
        select(ExternalItem)
        .join(
            latest,
            and_(
                ExternalItem.account_id == latest.c.account_id,
                ExternalItem.external_resource_id == latest.c.external_resource_id,
                ExternalItem.external_item_id == latest.c.external_item_id,
                ExternalItem.application_revision == latest.c.revision,
            ),
        )
        .join(ConnectorAccount, ConnectorAccount.id == ExternalItem.account_id)
        .where(
            _scope_clause(ExternalItem.project_id, request.scope),
            _scope_clause(ConnectorAccount.project_id, request.scope),
        )
    )
    if request.kinds:
        kinds = [
            kind.value
            for kind in request.kinds
            if KIND_FAMILY[kind] == ContextFamily.GITHUB
        ]
        statement = statement.where(ExternalItem.resource_type.in_(kinds))
    if request.states:
        states = [
            state.value
            for state in request.states
            if ContextFamily.GITHUB in STATE_FAMILIES[state]
        ]
        statement = statement.where(ExternalItem.state.in_(states))
    if request.query:
        pattern = f"%{request.query}%"
        statement = statement.where(
            or_(ExternalItem.title.ilike(pattern), ExternalItem.body.ilike(pattern))
        )
    return statement


def _github_text(item: ExternalItem) -> str:
    content = github_query._content(item)
    if isinstance(content, RepositoryExternalContent):
        return content.description or ""
    assert isinstance(content, NumberedExternalContent)
    return content.body or ""


def _github_items(session: Session, request: ContextHubQuery) -> list[ContextItem]:
    rows = list(
        session.scalars(
            _github_latest(request)
            .order_by(ExternalItem.application_revision.desc(), ExternalItem.id.desc())
            .limit(request.page_size + 1)
        )
    )
    return [
        ContextItem(
            family=ContextFamily.GITHUB,
            kind=ContextKind(item.resource_type),
            scope=request.scope,
            trust=TrustLabel.QUARANTINED_EXTERNAL,
            state=ContextState(item.state),
            title=_bounded(item.title, MAX_TITLE_CHARACTERS),
            text=_bounded(_github_text(item), MAX_TEXT_CHARACTERS),
            provenance=GitHubProvenance(
                account_id=item.account_id,
                external_resource_id=item.external_resource_id,
                external_item_id=item.external_item_id,
                revision_id=item.id,
                application_revision=item.application_revision,
            ),
            position=GitHubPosition(
                application_revision=item.application_revision, revision_id=item.id
            ),
        )
        for item in rows[: request.page_size]
    ]


def _calendar_items(session: Session, request: ContextHubQuery) -> list[ContextItem]:
    scope = calendar_query.CalendarExternalScope(request.scope.project_id)
    statement = calendar_query._latest_positive_query(scope)
    if request.query:
        statement = statement.where(
            CalendarEventRevision.title.ilike(f"%{request.query}%")
        )
    rows = list(
        session.scalars(
            statement.order_by(
                CalendarEventRevision.application_revision.desc(),
                CalendarEventRevision.id.desc(),
            ).limit(MAX_FAMILY_WORK)
        )
    )
    items: list[ContextItem] = []
    for event in rows:
        state, _, evidence_run_id = calendar_query.effective_evidence(session, event)
        typed_state = ContextState(state)
        if request.states and typed_state not in request.states:
            continue
        temporal = _calendar_temporal(event)
        items.append(
            ContextItem(
                family=ContextFamily.GOOGLE_CALENDAR,
                kind=ContextKind.CALENDAR_EVENT,
                scope=request.scope,
                trust=TrustLabel.QUARANTINED_EXTERNAL,
                state=typed_state,
                title=_bounded(event.title, MAX_TITLE_CHARACTERS),
                text=_bounded(temporal, MAX_TEXT_CHARACTERS),
                provenance=CalendarProvenance(
                    account_revision_id=event.account_revision_id,
                    calendar_identity_id=event.calendar_identity_id,
                    occurrence_key=event.occurrence_key,
                    event_revision_id=event.id,
                    application_revision=event.application_revision,
                    evidence_sync_run_id=evidence_run_id,
                ),
                position=CalendarPosition(
                    application_revision=event.application_revision,
                    revision_id=event.id,
                ),
            )
        )
        if len(items) == request.page_size:
            break
    return items


def query_context(session: Session, request: ContextHubQuery) -> ContextHubResult:
    """Federate fixed-order, bounded database-only family reads."""
    _require_scope(session, request.scope)
    adapters = {
        ContextFamily.LOCAL_SOURCE: _local_items,
        ContextFamily.GITHUB: _github_items,
        ContextFamily.GOOGLE_CALENDAR: _calendar_items,
    }
    groups = []
    for family in FAMILY_ORDER:
        if not _family_enabled(request, family):
            continue
        items = adapters[family](session, request)
        groups.append(
            ContextFamilyResult(
                family=family,
                items=tuple(items),
                exhausted=len(items) < request.page_size,
            )
        )
    return ContextHubResult(groups=tuple(groups))


def reopen_context(
    session: Session, scope: ContextScope, provenance: ContextProvenance
) -> ContextItem:
    """Resolve one exact immutable reference under the same mandatory scope."""
    _require_scope(session, scope)
    if isinstance(provenance, LocalSourceProvenance):
        row = session.execute(
            select(Source, SourceDocument, SourceChunk)
            .join(SourceDocument, SourceDocument.source_id == Source.id)
            .join(SourceChunk, SourceChunk.document_id == SourceDocument.id)
            .join(MemorySource, MemorySource.source_id == Source.id)
            .join(Memory, Memory.id == MemorySource.memory_id)
            .where(
                Source.id == provenance.source_id,
                SourceDocument.id == provenance.document_id,
                SourceChunk.id == provenance.chunk_id,
                SourceChunk.chunk_index == provenance.chunk_index,
                SourceChunk.content_hash == provenance.content_hash,
                SourceDocument.ingestion_status == "extracted",
                _scope_clause(Memory.project_id, scope),
            )
            .distinct()
        ).one_or_none()
        if row is None:
            raise ContextNotFoundError
        source, document, chunk = row
        request = ContextHubQuery(
            scope=scope, families=(ContextFamily.LOCAL_SOURCE,), page_size=1
        )
        return _local_item_from_exact(request, source, document, chunk)
    if isinstance(provenance, GitHubProvenance):
        item = session.scalar(
            select(ExternalItem)
            .join(ConnectorAccount, ConnectorAccount.id == ExternalItem.account_id)
            .where(
                ExternalItem.id == provenance.revision_id,
                ExternalItem.account_id == provenance.account_id,
                ExternalItem.external_resource_id == provenance.external_resource_id,
                ExternalItem.external_item_id == provenance.external_item_id,
                ExternalItem.application_revision == provenance.application_revision,
                _scope_clause(ExternalItem.project_id, scope),
                _scope_clause(ConnectorAccount.project_id, scope),
            )
        )
        if item is None:
            raise ContextNotFoundError
        return _github_item_from_exact(scope, item)
    event = session.scalar(
        select(CalendarEventRevision)
        .join(
            CalendarAccountRevision,
            CalendarAccountRevision.id == CalendarEventRevision.account_revision_id,
        )
        .where(
            CalendarEventRevision.id == provenance.event_revision_id,
            CalendarEventRevision.account_revision_id == provenance.account_revision_id,
            CalendarEventRevision.calendar_identity_id
            == provenance.calendar_identity_id,
            CalendarEventRevision.occurrence_key == provenance.occurrence_key,
            CalendarEventRevision.application_revision
            == provenance.application_revision,
            _scope_clause(CalendarEventRevision.project_id, scope),
            _scope_clause(CalendarAccountRevision.project_id, scope),
        )
    )
    run = session.scalar(
        select(CalendarSyncRun).where(
            CalendarSyncRun.id == provenance.evidence_sync_run_id,
            CalendarSyncRun.account_revision_id == provenance.account_revision_id,
            CalendarSyncRun.calendar_identity_id == provenance.calendar_identity_id,
            _scope_clause(CalendarSyncRun.project_id, scope),
            calendar_query._eligible_condition(),
        )
    )
    if event is None or run is None:
        raise ContextNotFoundError
    observed = session.scalar(
        select(CalendarEventObservation.id).where(
            CalendarEventObservation.sync_run_id == run.id,
            CalendarEventObservation.event_revision_id == event.id,
            CalendarEventObservation.occurrence_key == event.occurrence_key,
        )
    )
    state = ContextState.CURRENT if observed is not None else ContextState.STALE
    if observed is None and not calendar_query._covered(event, run):
        raise ContextNotFoundError
    return _calendar_item_from_exact(scope, event, run.id, state)


def _local_item_from_exact(
    request: ContextHubQuery,
    source: Source,
    document: SourceDocument,
    chunk: SourceChunk,
) -> ContextItem:
    return ContextItem(
        family=ContextFamily.LOCAL_SOURCE,
        kind=ContextKind.SOURCE_CHUNK,
        scope=request.scope,
        trust=TrustLabel.LOCAL_AUDITED,
        state=ContextState.EXTRACTED,
        title=_bounded(source.name, MAX_TITLE_CHARACTERS),
        text=_bounded(chunk.content, MAX_TEXT_CHARACTERS),
        provenance=LocalSourceProvenance(
            source_id=source.id,
            document_id=document.id,
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            content_hash=chunk.content_hash,
        ),
        position=LocalSourcePosition(
            source_created_at=source.created_at,
            source_id=source.id,
            chunk_index=chunk.chunk_index,
            chunk_id=chunk.id,
        ),
    )


def _github_item_from_exact(scope: ContextScope, item: ExternalItem) -> ContextItem:
    return ContextItem(
        family=ContextFamily.GITHUB,
        kind=ContextKind(item.resource_type),
        scope=scope,
        trust=TrustLabel.QUARANTINED_EXTERNAL,
        state=ContextState(item.state),
        title=_bounded(item.title, MAX_TITLE_CHARACTERS),
        text=_bounded(_github_text(item), MAX_TEXT_CHARACTERS),
        provenance=GitHubProvenance(
            account_id=item.account_id,
            external_resource_id=item.external_resource_id,
            external_item_id=item.external_item_id,
            revision_id=item.id,
            application_revision=item.application_revision,
        ),
        position=GitHubPosition(
            application_revision=item.application_revision, revision_id=item.id
        ),
    )


def _calendar_item_from_exact(
    scope: ContextScope,
    event: CalendarEventRevision,
    run_id: uuid.UUID,
    state: ContextState,
) -> ContextItem:
    temporal = _calendar_temporal(event)
    return ContextItem(
        family=ContextFamily.GOOGLE_CALENDAR,
        kind=ContextKind.CALENDAR_EVENT,
        scope=scope,
        trust=TrustLabel.QUARANTINED_EXTERNAL,
        state=state,
        title=_bounded(event.title, MAX_TITLE_CHARACTERS),
        text=_bounded(temporal, MAX_TEXT_CHARACTERS),
        provenance=CalendarProvenance(
            account_revision_id=event.account_revision_id,
            calendar_identity_id=event.calendar_identity_id,
            occurrence_key=event.occurrence_key,
            event_revision_id=event.id,
            application_revision=event.application_revision,
            evidence_sync_run_id=run_id,
        ),
        position=CalendarPosition(
            application_revision=event.application_revision, revision_id=event.id
        ),
    )


def _calendar_temporal(event: CalendarEventRevision) -> str:
    if event.all_day:
        assert event.start_date is not None and event.end_date is not None
        return f"{event.start_date.isoformat()} to {event.end_date.isoformat()}"
    assert event.start_instant is not None and event.end_instant is not None
    return f"{event.start_instant.isoformat()} to {event.end_instant.isoformat()}"
