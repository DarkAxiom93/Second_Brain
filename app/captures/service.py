"""Validated, concurrency-safe internal Capture creation."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.ingestion.text import chunk_text, hash_chunk, normalize_plain_text
from app.models.capture_item import CaptureItem
from app.models.source import Source
from app.repositories import capture_items as repository
from app.repositories import sources as source_repository
from app.repositories.projects import get_project
from app.schemas.capture import CaptureQueryRequest, CaptureScope
from app.schemas.source import SourceCreate
from app.sources.scope import get_source_for_scope

FINGERPRINT_DOMAIN = "second-brain.capture-create.v1"


class CaptureValidationError(ValueError):
    """Capture creation input is invalid."""


class CaptureProjectNotFoundError(Exception):
    """The exact assigned Project does not exist."""


class CaptureIdempotencyConflictError(Exception):
    """An idempotency key is already bound to another request."""


class CaptureNotFoundError(Exception):
    pass


class CaptureRevisionConflictError(Exception):
    def __init__(self, item: "CaptureItemProjection") -> None:
        self.item = item


class CaptureTransitionConflictError(Exception):
    pass


class CaptureSourceInvalidError(Exception):
    pass


@dataclass(frozen=True)
class CaptureCreate:
    content: str
    idempotency_key: str
    project_id: uuid.UUID | None = None


@dataclass(frozen=True)
class CaptureItemProjection:
    """Safe internal projection that deliberately omits private digests."""

    id: uuid.UUID
    project_id: uuid.UUID | None
    content: str
    state: str
    revision: int
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None
    resulting_source_id: uuid.UUID | None


@dataclass(frozen=True)
class CaptureCreateResult:
    item: CaptureItemProjection
    created: bool


@dataclass(frozen=True)
class CaptureConversionResult:
    item: CaptureItemProjection
    source: Source


def normalize_capture_content(value: str) -> str:
    """Normalize newlines while preserving all other meaningful whitespace."""

    normalized = normalize_plain_text(value)
    if "\x00" in normalized:
        raise CaptureValidationError("content must not contain NUL")
    if not normalized.strip():
        raise CaptureValidationError("content must contain a non-whitespace character")
    if len(normalized) > 8_000:
        raise CaptureValidationError("content exceeds 8000 Unicode scalar values")
    try:
        encoded = normalized.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CaptureValidationError(
            "content contains a non-scalar Unicode value"
        ) from exc
    if len(encoded) > 32_000:
        raise CaptureValidationError("content exceeds 32000 UTF-8 bytes")
    return normalized


def validate_idempotency_key(value: str) -> str:
    """Require 8-128 visible ASCII characters without altering the key."""

    invalid_character = any(not 0x21 <= ord(char) <= 0x7E for char in value)
    if not 8 <= len(value) <= 128 or invalid_character:
        raise CaptureValidationError(
            "idempotency key must be 8-128 visible ASCII characters"
        )
    return value


def hash_idempotency_key(value: str) -> str:
    return hashlib.sha256(validate_idempotency_key(value).encode("ascii")).hexdigest()


def request_fingerprint(content: str, project_id: uuid.UUID | None) -> str:
    """Hash the versioned normalized content and exact explicit scope."""

    scope = "unassigned" if project_id is None else f"project:{project_id}"
    canonical = json.dumps(
        {"content": content, "domain": FINGERPRINT_DOMAIN, "scope": scope},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _project(item: CaptureItem) -> CaptureItemProjection:
    return CaptureItemProjection(
        id=item.id,
        project_id=item.project_id,
        content=item.content,
        state=item.state,
        revision=item.revision,
        created_at=item.created_at,
        updated_at=item.updated_at,
        processed_at=item.processed_at,
        resulting_source_id=item.resulting_source_id,
    )


def scope_project_id(scope: CaptureScope) -> uuid.UUID | None:
    return scope.project_id


def validate_scope(session: Session, scope: CaptureScope) -> uuid.UUID | None:
    project_id = scope_project_id(scope)
    if project_id is not None and get_project(session, project_id) is None:
        raise CaptureProjectNotFoundError
    return project_id


def query_capture_items(
    session: Session,
    request: CaptureQueryRequest,
    position: tuple[datetime, uuid.UUID, float | None] | None = None,
) -> list[tuple[CaptureItemProjection, float | None]]:
    project_id = validate_scope(session, request.scope)
    return [
        (_project(item), rank)
        for item, rank in repository.query_captures(
            session,
            project_id=project_id,
            states=list(request.states),
            query=request.query,
            page_size=request.page_size,
            position=position,
        )
    ]


def detail_capture(
    session: Session, item_id: uuid.UUID, scope: CaptureScope
) -> CaptureItemProjection:
    project_id = validate_scope(session, scope)
    item = repository.get_scoped_capture(session, item_id, project_id)
    if item is None:
        raise CaptureNotFoundError
    return _project(item)


def _lock_pending(
    session: Session, item_id: uuid.UUID, scope: CaptureScope, revision: int
) -> CaptureItem:
    project_id = validate_scope(session, scope)
    item = repository.get_scoped_capture(session, item_id, project_id, lock=True)
    if item is None:
        raise CaptureNotFoundError
    if item.revision != revision:
        raise CaptureRevisionConflictError(_project(item))
    if item.state != "pending":
        raise CaptureTransitionConflictError
    return item


def _finish_mutation(session: Session, item: CaptureItem) -> CaptureItemProjection:
    item.revision += 1
    item.updated_at = datetime.now(UTC)
    session.flush()
    return _project(item)


def edit_capture(
    session: Session,
    item_id: uuid.UUID,
    scope: CaptureScope,
    revision: int,
    content: str,
) -> CaptureItemProjection:
    item = _lock_pending(session, item_id, scope, revision)
    item.content = normalize_capture_content(content)
    return _finish_mutation(session, item)


def reassign_capture(
    session: Session,
    item_id: uuid.UUID,
    scope: CaptureScope,
    target_scope: CaptureScope,
    revision: int,
) -> CaptureItemProjection:
    # Validate the destination before locking so the successful assigned-to-assigned
    # path remains within the approved four statements.
    target_project_id = validate_scope(session, target_scope)
    item = _lock_pending(session, item_id, scope, revision)
    item.project_id = target_project_id
    return _finish_mutation(session, item)


def transition_capture(
    session: Session,
    item_id: uuid.UUID,
    scope: CaptureScope,
    revision: int,
    *,
    expected: str,
    target: str,
) -> CaptureItemProjection:
    project_id = validate_scope(session, scope)
    item = repository.get_scoped_capture(session, item_id, project_id, lock=True)
    if item is None:
        raise CaptureNotFoundError
    if item.revision != revision:
        raise CaptureRevisionConflictError(_project(item))
    if item.state != expected:
        raise CaptureTransitionConflictError
    item.state = target
    return _finish_mutation(session, item)


def convert_capture(
    session: Session,
    item_id: uuid.UUID,
    scope: CaptureScope,
    revision: int,
) -> CaptureConversionResult:
    """Convert once, or resolve the one successful processed replay."""

    project_id = validate_scope(session, scope)
    item = repository.get_scoped_capture(session, item_id, project_id, lock=True)
    if item is None:
        raise CaptureNotFoundError
    if item.state == "processed":
        if revision not in {item.revision - 1, item.revision}:
            raise CaptureRevisionConflictError(_project(item))
        if item.resulting_source_id is None:
            raise CaptureSourceInvalidError
        source = get_source_for_scope(session, item.resulting_source_id, project_id)
        if source is None:
            raise CaptureSourceInvalidError
        return CaptureConversionResult(_project(item), source)
    if item.revision != revision:
        raise CaptureRevisionConflictError(_project(item))
    if item.state != "pending":
        raise CaptureTransitionConflictError

    source = source_repository.create_source(
        session,
        SourceCreate(
            source_type="capture",
            name=f"Capture {item.id}",
            reference=None,
            checksum=hash_chunk(item.content),
        ),
    )
    source_repository.upsert_text_document(
        session,
        source_id=source.id,
        normalized_text=item.content,
        original_filename=None,
        chunks=chunk_text(item.content, 2000, 200),
        extracted_at=datetime.now(UTC),
    )
    now = datetime.now(UTC)
    item.resulting_source_id = source.id
    item.processed_at = now
    item.state = "processed"
    item.revision += 1
    item.updated_at = now
    session.flush()
    return CaptureConversionResult(_project(item), source)


def resolve_capture_source(
    session: Session, item_id: uuid.UUID, scope: CaptureScope
) -> CaptureConversionResult:
    project_id = validate_scope(session, scope)
    item = repository.get_scoped_capture(session, item_id, project_id)
    if item is None:
        raise CaptureNotFoundError
    if item.state != "processed" or item.resulting_source_id is None:
        raise CaptureTransitionConflictError
    source = get_source_for_scope(session, item.resulting_source_id, project_id)
    if source is None:
        raise CaptureSourceInvalidError
    return CaptureConversionResult(_project(item), source)


def create_capture(session: Session, request: CaptureCreate) -> CaptureCreateResult:
    """Create or replay a Capture in at most three counted SQL statements."""

    content = normalize_capture_content(request.content)
    key_hash = hash_idempotency_key(request.idempotency_key)
    fingerprint = request_fingerprint(content, request.project_id)
    if (
        request.project_id is not None
        and get_project(session, request.project_id) is None
    ):
        raise CaptureProjectNotFoundError

    operation_time = datetime.now(UTC)
    item = repository.insert_capture_on_new_key(
        session,
        CaptureItem(
            id=uuid.uuid4(),
            project_id=request.project_id,
            content=content,
            state="pending",
            revision=1,
            created_at=operation_time,
            updated_at=operation_time,
            idempotency_key_hash=key_hash,
            request_fingerprint=fingerprint,
        ),
    )
    if item is not None:
        return CaptureCreateResult(item=_project(item), created=True)
    original = repository.get_capture_by_idempotency_hash(session, key_hash)
    assert original is not None
    if original.request_fingerprint != fingerprint:
        raise CaptureIdempotencyConflictError
    return CaptureCreateResult(item=_project(original), created=False)
