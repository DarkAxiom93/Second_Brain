"""Closed, account-scoped reads over quarantined ExternalItem revisions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from pydantic import ValidationError
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.connector import ConnectorAccount, ConnectorSyncRun, ExternalItem
from app.schemas.connector import (
    ConnectorScope,
    ExternalItemPage,
    ExternalItemRead,
    ExternalResourceType,
    NumberedExternalContent,
    ReconciliationState,
    RepositoryExternalContent,
)

MAX_PAGE_SIZE = 50
_CURSOR_DOMAIN = b"second-brain:external-items:v1"
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")


class ExternalItemNotFoundError(Exception):
    pass


class ExternalItemCursorError(Exception):
    pass


@dataclass(frozen=True)
class ExternalScope:
    project_id: uuid.UUID | None


def parse_scope(value: str) -> ExternalScope:
    if value == "unassigned":
        return ExternalScope(None)
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ValueError("invalid external item scope") from None
    if str(parsed) != value.lower():
        raise ValueError("invalid external item scope")
    return ExternalScope(parsed)


def _filter_key(
    account_id: uuid.UUID,
    scope: ExternalScope,
    resource_type: ExternalResourceType | None,
    state: ReconciliationState | None,
) -> str:
    raw = "|".join(
        (
            str(account_id),
            "unassigned" if scope.project_id is None else str(scope.project_id),
            resource_type or "*",
            state or "*",
        )
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _encode_cursor(item: ExternalItem, filter_key: str) -> str:
    payload = json.dumps(
        {"f": filter_key, "r": item.application_revision, "i": str(item.id)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    tag = hmac.new(_CURSOR_DOMAIN, payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(payload + tag).decode().rstrip("=")


def _decode_cursor(value: str, filter_key: str) -> tuple[int, uuid.UUID]:
    if not value or len(value) > 512 or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ExternalItemCursorError
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        payload, tag = raw[:-32], raw[-32:]
        expected = hmac.new(_CURSOR_DOMAIN, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected):
            raise ExternalItemCursorError
        decoded = json.loads(payload)
        if set(decoded) != {"f", "i", "r"} or decoded["f"] != filter_key:
            raise ExternalItemCursorError
        revision = decoded["r"]
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise ExternalItemCursorError
        return revision, uuid.UUID(decoded["i"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise ExternalItemCursorError from None


def _scoped_latest_query(
    account_id: uuid.UUID,
    scope: ExternalScope,
    resource_type: ExternalResourceType | None,
    state: ReconciliationState | None,
) -> Select[tuple[ExternalItem]]:
    latest = (
        select(
            ExternalItem.account_id,
            ExternalItem.external_resource_id,
            ExternalItem.external_item_id,
            func.max(ExternalItem.application_revision).label("max_revision"),
        )
        .where(ExternalItem.account_id == account_id)
        .group_by(
            ExternalItem.account_id,
            ExternalItem.external_resource_id,
            ExternalItem.external_item_id,
        )
        .subquery()
    )
    conditions = [
        ExternalItem.account_id == latest.c.account_id,
        ExternalItem.external_resource_id == latest.c.external_resource_id,
        ExternalItem.external_item_id == latest.c.external_item_id,
        ExternalItem.application_revision == latest.c.max_revision,
        ExternalItem.account_id == account_id,
        ExternalItem.project_id.is_(None)
        if scope.project_id is None
        else ExternalItem.project_id == scope.project_id,
    ]
    if resource_type is not None:
        conditions.append(ExternalItem.resource_type == resource_type)
    if state is not None:
        conditions.append(ExternalItem.state == state)
    return select(ExternalItem).join(latest, and_(*conditions))


def _require_account_scope(
    session: Session, account_id: uuid.UUID, scope: ExternalScope
) -> ConnectorAccount:
    account = session.get(ConnectorAccount, account_id)
    if account is None or account.project_id != scope.project_id:
        raise ExternalItemNotFoundError
    return account


def _content(item: ExternalItem) -> RepositoryExternalContent | NumberedExternalContent:
    try:
        value = json.loads(item.body)
        if not isinstance(value, dict):
            raise ExternalItemNotFoundError
        if item.resource_type == "repository":
            if set(value) != {"archived", "description", "private"}:
                raise ExternalItemNotFoundError
            return RepositoryExternalContent.model_validate(
                {"kind": "repository", **value}
            )
        if set(value) != {"body", "number", "state"}:
            raise ExternalItemNotFoundError
        return NumberedExternalContent.model_validate(
            {"kind": item.resource_type, **value}
        )
    except (json.JSONDecodeError, ValidationError):
        raise ExternalItemNotFoundError from None


def _repository_name(session: Session, item: ExternalItem) -> str | None:
    conditions = [
        ExternalItem.account_id == item.account_id,
        ExternalItem.external_resource_id == item.external_resource_id,
        ExternalItem.resource_type == "repository",
        ExternalItem.project_id.is_(None)
        if item.project_id is None
        else ExternalItem.project_id == item.project_id,
    ]
    name = session.scalar(
        select(ExternalItem.title)
        .where(*conditions)
        .order_by(ExternalItem.application_revision.asc())
        .limit(1)
    )
    return name if name is not None and _REPOSITORY_RE.fullmatch(name) else None


def _source_url(session: Session, item: ExternalItem, content: object) -> str | None:
    name = _repository_name(session, item)
    if name is None:
        return None
    base = f"https://github.com/{name}"
    if isinstance(content, RepositoryExternalContent):
        return base
    if isinstance(content, NumberedExternalContent):
        segment = "issues" if content.kind == "issue" else "pull"
        return f"{base}/{segment}/{content.number}"
    return None


def _confirmed_through(session: Session, item: ExternalItem) -> datetime | None:
    if item.state != "current":
        return None
    scope_condition = (
        ConnectorSyncRun.project_id.is_(None)
        if item.project_id is None
        else ConnectorSyncRun.project_id == item.project_id
    )
    return session.scalar(
        select(ConnectorSyncRun.completed_at)
        .where(
            ConnectorSyncRun.account_id == item.account_id,
            scope_condition,
            ConnectorSyncRun.status == "succeeded",
            ConnectorSyncRun.reconciliation_complete.is_(True),
        )
        .order_by(ConnectorSyncRun.completed_at.desc(), ConnectorSyncRun.id.desc())
        .limit(1)
    )


def _public(
    session: Session, item: ExternalItem, *, is_latest: bool
) -> ExternalItemRead:
    content = _content(item)
    return ExternalItemRead(
        id=item.id,
        account_id=item.account_id,
        provider="github",
        external_account_identity=item.external_account_id,
        scope=ConnectorScope(
            kind="unassigned" if item.project_id is None else "project",
            project_id=item.project_id,
        ),
        external_resource_id=item.external_resource_id,
        external_item_id=item.external_item_id,
        resource_type=cast(ExternalResourceType, item.resource_type),
        application_revision=item.application_revision,
        provider_source_version=item.provider_source_version,
        reconciliation_state=cast(ReconciliationState, item.state),
        title=item.title,
        content=content,
        first_seen_at=item.first_seen_at,
        revision_last_observed_at=item.last_seen_at,
        created_sync_run_id=item.created_sync_run_id,
        revision_last_observed_sync_run_id=item.last_seen_sync_run_id,
        confirmed_present_through=_confirmed_through(session, item),
        source_url=_source_url(session, item, content),
        is_latest=is_latest,
    )


def list_latest(
    session: Session,
    account_id: uuid.UUID,
    scope: ExternalScope,
    *,
    resource_type: ExternalResourceType | None,
    state: ReconciliationState | None,
    limit: int,
    cursor: str | None,
) -> ExternalItemPage:
    _require_account_scope(session, account_id, scope)
    key = _filter_key(account_id, scope, resource_type, state)
    query = _scoped_latest_query(account_id, scope, resource_type, state)
    if cursor is not None:
        revision, row_id = _decode_cursor(cursor, key)
        anchor = session.scalar(query.where(ExternalItem.id == row_id))
        if anchor is None or anchor.application_revision != revision:
            raise ExternalItemCursorError
        query = query.where(
            or_(
                ExternalItem.application_revision < revision,
                and_(
                    ExternalItem.application_revision == revision,
                    ExternalItem.id < row_id,
                ),
            )
        )
    rows = list(
        session.scalars(
            query.order_by(
                ExternalItem.application_revision.desc(), ExternalItem.id.desc()
            ).limit(limit + 1)
        )
    )
    page_rows = rows[:limit]
    return ExternalItemPage(
        items=[_public(session, item, is_latest=True) for item in page_rows],
        next_cursor=(
            _encode_cursor(page_rows[-1], key)
            if len(rows) > limit and page_rows
            else None
        ),
    )


def get_detail(
    session: Session, account_id: uuid.UUID, scope: ExternalScope, row_id: uuid.UUID
) -> ExternalItemRead:
    _require_account_scope(session, account_id, scope)
    item = session.scalar(
        _scoped_latest_query(account_id, scope, None, None).where(
            ExternalItem.id == row_id
        )
    )
    if item is None:
        raise ExternalItemNotFoundError
    return _public(session, item, is_latest=True)


def list_versions(
    session: Session, account_id: uuid.UUID, scope: ExternalScope, row_id: uuid.UUID
) -> list[ExternalItemRead]:
    latest = get_detail(session, account_id, scope, row_id)
    scope_condition = (
        ExternalItem.project_id.is_(None)
        if scope.project_id is None
        else ExternalItem.project_id == scope.project_id
    )
    rows = list(
        session.scalars(
            select(ExternalItem)
            .where(
                ExternalItem.account_id == account_id,
                scope_condition,
                ExternalItem.external_resource_id == latest.external_resource_id,
                ExternalItem.external_item_id == latest.external_item_id,
            )
            .order_by(ExternalItem.application_revision.desc())
            .limit(50)
        )
    )
    return [_public(session, item, is_latest=item.id == row_id) for item in rows]
