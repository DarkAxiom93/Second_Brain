"""Caller-transaction-owned primitives for inert connector persistence."""

import uuid
from datetime import datetime

from sqlalchemy import and_, exists, func, select, text
from sqlalchemy.orm import Session

from app.connectors.validation import (
    require_safe_code,
    validate_account_values,
    validate_item_values,
)
from app.models.connector import ConnectorAccount, ConnectorSyncRun, ExternalItem


class ConnectorOwnershipError(Exception):
    """A supplied child identity does not exactly match its owner."""


def create_account(session: Session, account: ConnectorAccount) -> ConnectorAccount:
    if account.provider is None:
        account.provider = "github"
    validate_account_values(
        provider=account.provider,
        external_account_id=account.external_account_id,
        external_account_fingerprint=account.external_account_fingerprint,
        credential_reference=account.credential_reference,
        resource_allowlist=account.resource_allowlist,
        granted_scope_fingerprint=account.granted_scope_fingerprint,
    )
    session.add(account)
    session.flush()
    session.refresh(account)
    return account


def get_account(session: Session, account_id: uuid.UUID) -> ConnectorAccount | None:
    return session.scalar(
        select(ConnectorAccount).where(ConnectorAccount.id == account_id)
    )


def list_accounts(
    session: Session, *, limit: int, offset: int
) -> list[ConnectorAccount]:
    return list(
        session.scalars(
            select(ConnectorAccount)
            .order_by(ConnectorAccount.created_at.desc(), ConnectorAccount.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def lock_account(session: Session, account_id: uuid.UUID) -> ConnectorAccount | None:
    return session.scalar(
        select(ConnectorAccount)
        .where(ConnectorAccount.id == account_id)
        .with_for_update(of=ConnectorAccount)
    )


def increment_account_revision(
    session: Session, account_id: uuid.UUID
) -> ConnectorAccount | None:
    account = lock_account(session, account_id)
    if account is not None:
        account.revision += 1
        session.flush()
    return account


def has_active_sync_run(session: Session, account_id: uuid.UUID) -> bool:
    return bool(
        session.scalar(
            select(
                exists().where(
                    ConnectorSyncRun.account_id == account_id,
                    ConnectorSyncRun.status.in_(("claimed", "running")),
                )
            )
        )
    )


def lock_sync_capacity(session: Session) -> None:
    """Serialize global active-sync capacity accounting without schema changes."""

    session.execute(text("SELECT pg_advisory_xact_lock(910004)"))


def active_sync_count(session: Session) -> int:
    return int(
        session.scalar(
            select(func.count(ConnectorSyncRun.id)).where(
                ConnectorSyncRun.status.in_(("claimed", "running"))
            )
        )
        or 0
    )


def get_sync_run(session: Session, run_id: uuid.UUID) -> ConnectorSyncRun | None:
    return session.get(ConnectorSyncRun, run_id)


def latest_sync_run(session: Session, account_id: uuid.UUID) -> ConnectorSyncRun | None:
    return session.scalar(
        select(ConnectorSyncRun)
        .where(ConnectorSyncRun.account_id == account_id)
        .order_by(ConnectorSyncRun.created_at.desc(), ConnectorSyncRun.id.desc())
        .limit(1)
    )


def latest_repository_snapshot(
    session: Session, account_id: uuid.UUID, repository_name: str
) -> ExternalItem | None:
    """Return prior repository identity by its validated case-insensitive name."""

    return session.scalar(
        select(ExternalItem)
        .where(
            ExternalItem.account_id == account_id,
            ExternalItem.resource_type == "repository",
            func.lower(ExternalItem.title) == repository_name.casefold(),
        )
        .order_by(ExternalItem.application_revision.desc())
        .limit(1)
    )


def create_sync_run(session: Session, run: ConnectorSyncRun) -> ConnectorSyncRun:
    require_safe_code(run.trigger_identity)
    if run.safe_error_code is not None:
        require_safe_code(run.safe_error_code)
    account = get_account(session, run.account_id)
    if account is None or (account.provider, account.external_account_id) != (
        run.provider,
        run.external_account_id,
    ):
        raise ConnectorOwnershipError
    if (run.account_revision, run.project_id) != (account.revision, account.project_id):
        raise ConnectorOwnershipError
    session.add(run)
    session.flush()
    session.refresh(run)
    return run


def record_item_revision(
    session: Session, item: ExternalItem, *, seen_at: datetime
) -> tuple[ExternalItem, bool]:
    """Return exact replay write-free, or append the next deterministic revision."""

    validate_item_values(
        provider=item.provider,
        resource_type=item.resource_type,
        external_resource_id=item.external_resource_id,
        external_item_id=item.external_item_id,
        provider_source_version=item.provider_source_version,
        title=item.title,
        body=item.body,
        content_hash=item.content_hash,
    )
    run = session.scalar(
        select(ConnectorSyncRun).where(
            ConnectorSyncRun.id == item.created_sync_run_id,
            ConnectorSyncRun.account_id == item.account_id,
            ConnectorSyncRun.provider == item.provider,
        )
    )
    if run is None or (run.external_account_id, run.project_id) != (
        item.external_account_id,
        item.project_id,
    ):
        raise ConnectorOwnershipError
    existing = session.scalar(
        select(ExternalItem).where(
            ExternalItem.account_id == item.account_id,
            ExternalItem.external_resource_id == item.external_resource_id,
            ExternalItem.external_item_id == item.external_item_id,
            ExternalItem.provider_source_version == item.provider_source_version,
            ExternalItem.content_hash == item.content_hash,
        )
    )
    if existing is not None:
        return existing, False
    latest = session.scalar(
        select(ExternalItem)
        .where(
            ExternalItem.account_id == item.account_id,
            ExternalItem.external_resource_id == item.external_resource_id,
            ExternalItem.external_item_id == item.external_item_id,
        )
        .order_by(ExternalItem.application_revision.desc())
        .limit(1)
        .with_for_update(of=ExternalItem)
    )
    item.application_revision = 1 if latest is None else latest.application_revision + 1
    item.first_seen_at = seen_at if latest is None else latest.first_seen_at
    item.last_seen_at = seen_at
    session.add(item)
    session.flush()
    session.refresh(item)
    return item, True


def reconcile_latest_items(
    session: Session,
    run: ConnectorSyncRun,
    observed: set[tuple[str, str]],
    *,
    reconciled_at: datetime,
) -> None:
    """Reconcile only latest exact identities after a complete fenced run."""

    latest = (
        select(
            ExternalItem.account_id,
            ExternalItem.external_resource_id,
            ExternalItem.external_item_id,
            func.max(ExternalItem.application_revision).label("max_revision"),
        )
        .where(ExternalItem.account_id == run.account_id)
        .group_by(
            ExternalItem.account_id,
            ExternalItem.external_resource_id,
            ExternalItem.external_item_id,
        )
        .subquery()
    )
    rows = list(
        session.scalars(
            select(ExternalItem)
            .join(
                latest,
                and_(
                    ExternalItem.account_id == latest.c.account_id,
                    ExternalItem.external_resource_id == latest.c.external_resource_id,
                    ExternalItem.external_item_id == latest.c.external_item_id,
                    ExternalItem.application_revision == latest.c.max_revision,
                ),
            )
            .where(
                ExternalItem.account_id == run.account_id,
                ExternalItem.project_id.is_(None)
                if run.project_id is None
                else ExternalItem.project_id == run.project_id,
            )
            .with_for_update(of=ExternalItem)
        )
    )
    for item in rows:
        target = (
            "current"
            if (item.external_resource_id, item.external_item_id) in observed
            else "stale"
        )
        if item.state != target:
            item.state = target
            if target == "current":
                item.last_seen_at = reconciled_at
                item.last_seen_sync_run_id = run.id
    session.flush()
