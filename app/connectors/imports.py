"""Explicit, network-free import of one quarantined ExternalItem revision."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.connectors import query as item_query
from app.ingestion.text import chunk_text, normalize_plain_text
from app.models.connector import ConnectorAccount, ExternalItem
from app.models.external_item_import import ExternalItemImport
from app.models.source import Source
from app.models.source_chunk import SourceChunk
from app.models.source_document import SourceDocument
from app.schemas.connector import (
    ConnectorScope,
    ExternalItemImportConfirm,
    ExternalItemImportPreview,
    ExternalResourceType,
    NumberedExternalContent,
    RepositoryExternalContent,
)

CHUNK_SIZE = 2_000
CHUNK_OVERLAP = 200
SOURCE_TYPE = "connector_import"
_FINGERPRINT_DOMAIN = "second-brain:external-item-import:v1"


class ExternalItemImportNotFoundError(Exception):
    pass


class ExternalItemImportConflictError(Exception):
    pass


@dataclass(frozen=True)
class ImportResult:
    provenance: ExternalItemImport
    source: Source
    document: SourceDocument
    chunk_count: int
    created: bool


def _scope_condition(item: ExternalItem, scope: item_query.ExternalScope) -> bool:
    return item.project_id == scope.project_id


def _normalized_text(item: ExternalItem, content: object) -> str:
    title = item.title.strip() or "Untitled GitHub item"
    if isinstance(content, RepositoryExternalContent):
        description = content.description or "(no description)"
        raw = (
            f"{title}\n\nRepository description:\n{description}\n\n"
            f"Private: {str(content.private).lower()}\n"
            f"Archived: {str(content.archived).lower()}"
        )
    elif isinstance(content, NumberedExternalContent):
        label = "Issue" if content.kind == "issue" else "Pull request"
        body = content.body or "(no body)"
        raw = f"{title}\n\n{label} #{content.number} ({content.state})\n\n{body}"
    else:  # pragma: no cover - closed content models make this unreachable
        raise ExternalItemImportConflictError
    return normalize_plain_text(raw)


def _preview_values(session: Session, item: ExternalItem) -> ExternalItemImportPreview:
    try:
        content = item_query._content(item)
        source_url = item_query._source_url(session, item, content)
    except item_query.ExternalItemNotFoundError:
        raise ExternalItemImportConflictError from None
    return ExternalItemImportPreview(
        account_id=item.account_id,
        external_item_row_id=item.id,
        external_resource_id=item.external_resource_id,
        external_item_id=item.external_item_id,
        application_revision=item.application_revision,
        trust="external_untrusted",
        scope=ConnectorScope(
            kind="unassigned" if item.project_id is None else "project",
            project_id=item.project_id,
        ),
        resource_type=cast(ExternalResourceType, item.resource_type),
        title=item.title,
        normalized_text=_normalized_text(item, content),
        provider_source_version=item.provider_source_version,
        content_hash=item.content_hash,
        canonical_source_url=source_url,
        confirmation_fingerprint="0" * 64,
    )


def _fingerprint(values: ExternalItemImportPreview) -> str:
    canonical = json.dumps(
        {
            "domain": _FINGERPRINT_DOMAIN,
            **values.model_dump(mode="json", exclude={"confirmation_fingerprint"}),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _latest_revision(session: Session, item: ExternalItem) -> int | None:
    return session.scalar(
        select(func.max(ExternalItem.application_revision)).where(
            ExternalItem.account_id == item.account_id,
            ExternalItem.external_resource_id == item.external_resource_id,
            ExternalItem.external_item_id == item.external_item_id,
        )
    )


def _require_item(
    session: Session,
    account_id: uuid.UUID,
    scope: item_query.ExternalScope,
    row_id: uuid.UUID,
    *,
    lock: bool,
) -> ExternalItem:
    if session.get(ConnectorAccount, account_id) is None:
        raise ExternalItemImportNotFoundError
    statement = select(ExternalItem).where(
        ExternalItem.id == row_id, ExternalItem.account_id == account_id
    )
    if lock:
        statement = statement.with_for_update()
    item = session.scalar(statement)
    if item is None or not _scope_condition(item, scope):
        raise ExternalItemImportNotFoundError
    if (
        item.state != "current"
        or _latest_revision(session, item) != item.application_revision
    ):
        raise ExternalItemImportConflictError
    return item


def preview(
    session: Session,
    account_id: uuid.UUID,
    scope: item_query.ExternalScope,
    row_id: uuid.UUID,
) -> ExternalItemImportPreview:
    """Return a mutation-free preview for one exact current latest revision."""
    item = _require_item(session, account_id, scope, row_id, lock=False)
    values = _preview_values(session, item)
    return values.model_copy(update={"confirmation_fingerprint": _fingerprint(values)})


def _existing_result(session: Session, provenance: ExternalItemImport) -> ImportResult:
    document = session.get(SourceDocument, provenance.source_document_id)
    if document is None:
        raise ExternalItemImportConflictError
    source = session.get(Source, document.source_id)
    if source is None:
        raise ExternalItemImportConflictError
    count = session.scalar(
        select(func.count(SourceChunk.id)).where(SourceChunk.document_id == document.id)
    )
    return ImportResult(provenance, source, document, int(count or 0), False)


def confirm(
    session: Session,
    account_id: uuid.UUID,
    scope: item_query.ExternalScope,
    row_id: uuid.UUID,
    request: ExternalItemImportConfirm,
) -> ImportResult:
    """Atomically stage one exact import; the caller owns commit/rollback."""
    item = _require_item(session, account_id, scope, row_id, lock=True)
    values = _preview_values(session, item)
    fingerprint = _fingerprint(values)
    if (
        request.application_revision != item.application_revision
        or request.provider_source_version != item.provider_source_version
        or request.content_hash != item.content_hash
        or request.confirmation_fingerprint != fingerprint
    ):
        raise ExternalItemImportConflictError

    existing = session.scalar(
        select(ExternalItemImport).where(ExternalItemImport.external_item_id == item.id)
    )
    if existing is not None:
        if existing.confirmation_fingerprint != fingerprint:
            raise ExternalItemImportConflictError
        return _existing_result(session, existing)

    normalized_text = values.normalized_text
    chunks = chunk_text(normalized_text, CHUNK_SIZE, CHUNK_OVERLAP)
    source_name = (item.title.strip() or f"GitHub {item.resource_type}")[:255]
    source = Source(
        source_type=SOURCE_TYPE,
        name=source_name,
        reference=values.canonical_source_url,
        checksum=item.content_hash,
    )
    session.add(source)
    session.flush()
    document = SourceDocument(
        source_id=source.id,
        media_type="text/plain",
        original_filename=None,
        byte_size=len(normalized_text.encode("utf-8")),
        extracted_text=normalized_text,
        ingestion_status="extracted",
        error_code=None,
        extracted_at=datetime.now(UTC),
    )
    document.chunks = [SourceChunk(**chunk.__dict__) for chunk in chunks]
    session.add(document)
    session.flush()
    provenance = ExternalItemImport(
        external_item_id=item.id,
        source_document_id=document.id,
        confirmation_fingerprint=fingerprint,
        canonical_source_url=values.canonical_source_url,
    )
    session.add(provenance)
    session.flush()
    return ImportResult(provenance, source, document, len(chunks), True)
