"""Inert persistence models for quarantined connector metadata and snapshots."""

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

_SAFE_CODE_PATTERN = "^[a-z][a-z0-9_]{0,99}$"
_IDENTITY_PATTERN = "^[A-Za-z0-9][A-Za-z0-9:._-]{0,254}$"
_SHA256_PATTERN = "^[0-9a-f]{64}$"
_CREDENTIAL_PATTERN = (
    "^sbcred:v1:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_SECRET_MARKERS = (
    "ghp_",
    "github_pat_",
    "bearer ",
    "authorization",
    "password",
    "client_secret",
    "refresh_token",
    "access_token",
    "cookie",
)


def _no_secret_markers(column: str) -> str:
    return " AND ".join(
        f"position('{marker}' in lower({column})) = 0" for marker in _SECRET_MARKERS
    )


class ConnectorAccount(Base):
    """Safe account metadata; a null Project is explicitly unassigned."""

    __tablename__ = "connector_accounts"
    __table_args__ = (
        CheckConstraint("provider = 'github'", name="ck_connector_accounts_provider"),
        CheckConstraint(
            f"external_account_id ~ '{_IDENTITY_PATTERN}' AND "
            f"{_no_secret_markers('external_account_id')}",
            name="ck_connector_accounts_external_identity",
        ),
        CheckConstraint(
            f"external_account_fingerprint ~ '{_SHA256_PATTERN}'",
            name="ck_connector_accounts_external_fingerprint",
        ),
        CheckConstraint(
            f"credential_reference ~ '{_CREDENTIAL_PATTERN}'",
            name="ck_connector_accounts_credential_reference",
        ),
        CheckConstraint(
            f"granted_scope_fingerprint ~ '{_SHA256_PATTERN}'",
            name="ck_connector_accounts_scope_fingerprint",
        ),
        CheckConstraint(
            "cardinality(resource_allowlist) BETWEEN 1 AND 32 "
            "AND array_position(resource_allowlist, NULL) IS NULL",
            name="ck_connector_accounts_resource_allowlist",
        ),
        CheckConstraint(
            "lifecycle IN ('disabled','enabled','revoked')",
            name="ck_connector_accounts_lifecycle",
        ),
        CheckConstraint(
            "validation_status IN "
            "('unvalidated','valid','invalid','expired','revoked')",
            name="ck_connector_accounts_validation_status",
        ),
        CheckConstraint("revision >= 0", name="ck_connector_accounts_revision"),
        CheckConstraint(
            "last_validated_at IS NULL OR last_validated_at >= created_at",
            name="ck_connector_accounts_validation_order",
        ),
        UniqueConstraint(
            "provider",
            "external_account_id",
            name="uq_connector_accounts_provider_external_identity",
        ),
        UniqueConstraint(
            "credential_reference",
            name="uq_connector_accounts_credential_reference",
        ),
        UniqueConstraint(
            "id", "provider", "external_account_id", name="uq_connector_accounts_owner"
        ),
        Index(
            "ix_connector_accounts_project_created", "project_id", "created_at", "id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="github", server_default="github"
    )
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_account_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    credential_reference: Mapped[str] = mapped_column(String(46), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
    )
    resource_allowlist: Mapped[list[str]] = mapped_column(
        ARRAY(String(255)), nullable=False
    )
    granted_scope_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle: Mapped[str] = mapped_column(
        String(16), nullable=False, default="disabled", server_default="disabled"
    )
    validation_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unvalidated", server_default="unvalidated"
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    sync_runs: Mapped[list["ConnectorSyncRun"]] = relationship(
        back_populates="account", passive_deletes=True
    )
    items: Mapped[list["ExternalItem"]] = relationship(
        back_populates="account", passive_deletes=True
    )


class ConnectorSyncRun(Base):
    """Bounded content-free audit state for a future connector read."""

    __tablename__ = "connector_sync_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id", "provider", "external_account_id"],
            [
                "connector_accounts.id",
                "connector_accounts.provider",
                "connector_accounts.external_account_id",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint("provider = 'github'", name="ck_connector_sync_runs_provider"),
        CheckConstraint(
            f"external_account_id ~ '{_IDENTITY_PATTERN}' AND "
            f"{_no_secret_markers('external_account_id')}",
            name="ck_connector_sync_runs_external_identity",
        ),
        CheckConstraint(
            "account_revision >= 0", name="ck_connector_sync_runs_account_revision"
        ),
        CheckConstraint(
            "trigger_kind IN ('manual','scheduled')",
            name="ck_connector_sync_runs_trigger_kind",
        ),
        CheckConstraint(
            f"trigger_identity ~ '{_SAFE_CODE_PATTERN}' AND "
            f"{_no_secret_markers('trigger_identity')}",
            name="ck_connector_sync_runs_trigger_identity",
        ),
        CheckConstraint(
            "status IN "
            "('claimed','running','succeeded','incomplete','failed','cancelled')",
            name="ck_connector_sync_runs_status",
        ),
        CheckConstraint(
            "items_seen BETWEEN 0 AND 100000 AND items_created BETWEEN 0 AND 100000 "
            "AND items_unchanged BETWEEN 0 AND 100000",
            name="ck_connector_sync_runs_counts",
        ),
        CheckConstraint(
            f"safe_error_code IS NULL OR (safe_error_code ~ '{_SAFE_CODE_PATTERN}' AND "
            f"{_no_secret_markers('safe_error_code')})",
            name="ck_connector_sync_runs_error_code",
        ),
        CheckConstraint(
            "(status IN ('succeeded','incomplete','failed','cancelled')) = "
            "(completed_at IS NOT NULL)",
            name="ck_connector_sync_runs_completion",
        ),
        CheckConstraint(
            "reconciliation_complete = false OR status = 'succeeded'",
            name="ck_connector_sync_runs_reconciliation",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at",
            name="ck_connector_sync_runs_timestamp_order",
        ),
        UniqueConstraint(
            "id", "account_id", "provider", name="uq_connector_sync_runs_provenance"
        ),
        Index(
            "uq_connector_sync_runs_one_active_account",
            "account_id",
            unique=True,
            postgresql_where=text("status IN ('claimed','running')"),
        ),
        Index(
            "ix_connector_sync_runs_account_created", "account_id", "created_at", "id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    account_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
    )
    trigger_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    trigger_identity: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="claimed", server_default="claimed"
    )
    items_seen: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    items_created: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    items_unchanged: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    safe_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reconciliation_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    account: Mapped[ConnectorAccount] = relationship(back_populates="sync_runs")
    created_items: Mapped[list["ExternalItem"]] = relationship(
        foreign_keys="ExternalItem.created_sync_run_id", passive_deletes=True
    )
    seen_items: Mapped[list["ExternalItem"]] = relationship(
        foreign_keys="ExternalItem.last_seen_sync_run_id", passive_deletes=True
    )


class ExternalItem(Base):
    """One append-only quarantined item revision with exact provenance."""

    __tablename__ = "external_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id", "provider", "external_account_id"],
            [
                "connector_accounts.id",
                "connector_accounts.provider",
                "connector_accounts.external_account_id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["created_sync_run_id", "account_id", "provider"],
            [
                "connector_sync_runs.id",
                "connector_sync_runs.account_id",
                "connector_sync_runs.provider",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["last_seen_sync_run_id", "account_id", "provider"],
            [
                "connector_sync_runs.id",
                "connector_sync_runs.account_id",
                "connector_sync_runs.provider",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint("provider = 'github'", name="ck_external_items_provider"),
        CheckConstraint(
            f"external_resource_id ~ '{_IDENTITY_PATTERN}' AND "
            f"{_no_secret_markers('external_resource_id')}",
            name="ck_external_items_resource_identity",
        ),
        CheckConstraint(
            f"external_item_id ~ '{_IDENTITY_PATTERN}' AND "
            f"{_no_secret_markers('external_item_id')}",
            name="ck_external_items_item_identity",
        ),
        CheckConstraint(
            "resource_type IN ('repository','issue','pull_request')",
            name="ck_external_items_resource_type",
        ),
        CheckConstraint(
            "char_length(provider_source_version) BETWEEN 1 AND 255 AND "
            f"{_no_secret_markers('provider_source_version')}",
            name="ck_external_items_source_version",
        ),
        CheckConstraint(
            "char_length(title) BETWEEN 0 AND 500 AND octet_length(title) <= 2000",
            name="ck_external_items_title_size",
        ),
        CheckConstraint(
            "char_length(body) BETWEEN 0 AND 20000 AND octet_length(body) <= 80000",
            name="ck_external_items_body_size",
        ),
        CheckConstraint(
            f"content_hash ~ '{_SHA256_PATTERN}'", name="ck_external_items_content_hash"
        ),
        CheckConstraint("application_revision >= 1", name="ck_external_items_revision"),
        CheckConstraint(
            "state IN ('current','stale','deleted')", name="ck_external_items_state"
        ),
        CheckConstraint(
            "last_seen_at >= first_seen_at", name="ck_external_items_seen_order"
        ),
        UniqueConstraint(
            "account_id",
            "external_resource_id",
            "external_item_id",
            "application_revision",
            name="uq_external_items_application_revision",
        ),
        UniqueConstraint(
            "account_id",
            "external_resource_id",
            "external_item_id",
            "provider_source_version",
            "content_hash",
            name="uq_external_items_provider_replay",
        ),
        Index(
            "ix_external_items_identity_revision",
            "account_id",
            "external_resource_id",
            "external_item_id",
            "application_revision",
        ),
        Index(
            "ix_external_items_project_state",
            "project_id",
            "state",
            "last_seen_at",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_source_version: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(
        String(500), nullable=False, default="", server_default=""
    )
    body: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    application_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="current", server_default="current"
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_sync_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    last_seen_sync_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    account: Mapped[ConnectorAccount] = relationship(back_populates="items")
