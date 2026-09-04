"""Provider-specific inert Google Calendar persistence."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

_SHA256 = "^[0-9a-f]{64}$"
_CREDENTIAL = (
    "^sbcred:v1:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_SAFE_CODE = "^[a-z][a-z0-9_]{0,99}$"


class CalendarAccountRevision(Base):
    __tablename__ = "calendar_account_revisions"
    __table_args__ = (
        CheckConstraint(
            "provider = 'google_calendar'", name="ck_calendar_accounts_provider"
        ),
        CheckConstraint(
            f"account_fingerprint ~ '{_SHA256}'",
            name="ck_calendar_accounts_fingerprint",
        ),
        CheckConstraint(
            f"credential_reference ~ '{_CREDENTIAL}'",
            name="ck_calendar_accounts_credential",
        ),
        CheckConstraint(
            "configuration_revision >= 1", name="ck_calendar_accounts_revision"
        ),
        CheckConstraint(
            "lifecycle IN ('disabled','enabled','revoked')",
            name="ck_calendar_accounts_lifecycle",
        ),
        CheckConstraint(
            "configuration_state IN "
            "('configured','invalid','reauthorization_required')",
            name="ck_calendar_accounts_state",
        ),
        UniqueConstraint(
            "configuration_id",
            "configuration_revision",
            name="uq_calendar_accounts_config_revision",
        ),
        UniqueConstraint(
            "id", "account_fingerprint", name="uq_calendar_accounts_owner"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    configuration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    configuration_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="google_calendar",
        server_default="google_calendar",
    )
    account_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_reference: Mapped[str] = mapped_column(String(46), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
    )
    lifecycle: Mapped[str] = mapped_column(
        String(16), nullable=False, default="disabled", server_default="disabled"
    )
    configuration_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="configured", server_default="configured"
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
    calendars: Mapped[list["CalendarIdentity"]] = relationship(
        back_populates="account", passive_deletes=True
    )


class CalendarIdentity(Base):
    __tablename__ = "calendar_identities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_revision_id", "account_fingerprint"],
            [
                "calendar_account_revisions.id",
                "calendar_account_revisions.account_fingerprint",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "char_length(provider_calendar_id) BETWEEN 1 AND 1024 AND "
            "octet_length(provider_calendar_id) <= 4096",
            name="ck_calendar_identities_id_size",
        ),
        UniqueConstraint(
            "account_revision_id",
            "provider_calendar_id",
            name="uq_calendar_identities_exact",
        ),
        UniqueConstraint(
            "id", "account_revision_id", name="uq_calendar_identities_owner"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    account_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_calendar_id: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    account: Mapped[CalendarAccountRevision] = relationship(back_populates="calendars")


class CalendarSyncRun(Base):
    __tablename__ = "calendar_sync_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["calendar_identity_id", "account_revision_id"],
            ["calendar_identities.id", "calendar_identities.account_revision_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("window_end > window_start", name="ck_calendar_sync_window"),
        CheckConstraint(
            "window_end <= window_start + interval '90 days'",
            name="ck_calendar_sync_window_bound",
        ),
        CheckConstraint(
            "trigger_kind IN ('manual','scheduled')", name="ck_calendar_sync_trigger"
        ),
        CheckConstraint(
            "status IN "
            "('claimed','running','succeeded','incomplete','failed','cancelled')",
            name="ck_calendar_sync_status",
        ),
        CheckConstraint(
            "completeness IN ('unknown','complete','incomplete')",
            name="ck_calendar_sync_completeness",
        ),
        CheckConstraint(
            "items_seen BETWEEN 0 AND 5000 AND "
            "items_written BETWEEN 0 AND 5000 AND "
            "items_unchanged BETWEEN 0 AND 5000",
            name="ck_calendar_sync_counts",
        ),
        CheckConstraint(
            f"safe_failure_code IS NULL OR safe_failure_code ~ '{_SAFE_CODE}'",
            name="ck_calendar_sync_failure",
        ),
        CheckConstraint(
            "(status IN ('succeeded','incomplete','failed','cancelled')) = "
            "(completed_at IS NOT NULL)",
            name="ck_calendar_sync_completion",
        ),
        CheckConstraint(
            "completeness != 'complete' OR status = 'succeeded'",
            name="ck_calendar_sync_complete_status",
        ),
        CheckConstraint(
            "observation_evidence_version IS NULL OR "
            "observation_evidence_version = 'calendar-observations-v1'",
            name="ck_calendar_sync_observation_evidence_version",
        ),
        CheckConstraint(
            "started_at IS NULL OR started_at >= created_at",
            name="ck_calendar_sync_started",
        ),
        CheckConstraint(
            "completed_at IS NULL OR "
            "(started_at IS NOT NULL AND completed_at >= started_at)",
            name="ck_calendar_sync_completed",
        ),
        UniqueConstraint(
            "id",
            "calendar_identity_id",
            "account_revision_id",
            name="uq_calendar_sync_provenance",
        ),
        Index(
            "uq_calendar_sync_one_active",
            "calendar_identity_id",
            unique=True,
            postgresql_where=text("status IN ('claimed','running')"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    calendar_identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
    )
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    trigger_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="claimed", server_default="claimed"
    )
    completeness: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unknown", server_default="unknown"
    )
    items_seen: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    items_written: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    items_unchanged: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    safe_failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    observation_evidence_version: Mapped[str | None] = mapped_column(
        String(32), nullable=True
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


class CalendarEventRevision(Base):
    __tablename__ = "calendar_event_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["sync_run_id", "calendar_identity_id", "account_revision_id"],
            [
                "calendar_sync_runs.id",
                "calendar_sync_runs.calendar_identity_id",
                "calendar_sync_runs.account_revision_id",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "char_length(provider_event_id) BETWEEN 1 AND 1024 AND "
            "octet_length(provider_event_id) <= 4096",
            name="ck_calendar_events_event_id",
        ),
        CheckConstraint(
            "char_length(occurrence_key) BETWEEN 1 AND 2200 AND "
            "octet_length(occurrence_key) <= 8800",
            name="ck_calendar_events_occurrence_key",
        ),
        CheckConstraint(
            "event_type IN "
            "('default','focus_time','out_of_office','working_location','birthday')",
            name="ck_calendar_events_type",
        ),
        CheckConstraint(
            "state IN ('current','stale','cancelled','deleted')",
            name="ck_calendar_events_state",
        ),
        CheckConstraint(f"content_hash ~ '{_SHA256}'", name="ck_calendar_events_hash"),
        CheckConstraint(
            "application_revision >= 1", name="ck_calendar_events_revision"
        ),
        CheckConstraint(
            "char_length(title) BETWEEN 1 AND 500 AND octet_length(title) <= 2000",
            name="ck_calendar_events_title",
        ),
        CheckConstraint(
            "(all_day AND start_date IS NOT NULL AND end_date IS NOT NULL AND "
            "start_instant IS NULL AND end_instant IS NULL AND end_date > start_date) "
            "OR (NOT all_day AND start_date IS NULL AND end_date IS NULL AND "
            "start_instant IS NOT NULL AND end_instant IS NOT NULL AND "
            "end_instant > start_instant)",
            name="ck_calendar_events_temporal_shape",
        ),
        CheckConstraint(
            "(original_start_date IS NULL) OR (original_start_instant IS NULL)",
            name="ck_calendar_events_original_shape",
        ),
        CheckConstraint(
            "(recurring_series_id IS NULL AND original_start_date IS NULL AND "
            "original_start_instant IS NULL) OR (recurring_series_id IS NOT NULL "
            "AND ((original_start_date IS NOT NULL) <> "
            "(original_start_instant IS NOT NULL)))",
            name="ck_calendar_events_recurrence_shape",
        ),
        CheckConstraint(
            "(is_private AND title = 'Busy') OR (NOT is_private AND "
            "((event_type = 'default') OR title IN "
            "('Focus time','Out of office','Working location','Birthday')))",
            name="ck_calendar_events_minimized_title",
        ),
        CheckConstraint(
            "event_type = 'default' OR is_private OR title IN "
            "('Focus time','Out of office','Working location','Birthday')",
            name="ck_calendar_events_special_title",
        ),
        CheckConstraint(
            "last_seen_at >= first_seen_at", name="ck_calendar_events_seen"
        ),
        UniqueConstraint(
            "calendar_identity_id",
            "occurrence_key",
            "application_revision",
            name="uq_calendar_events_revision",
        ),
        UniqueConstraint(
            "calendar_identity_id",
            "occurrence_key",
            "provider_etag",
            "content_hash",
            name="uq_calendar_events_replay",
        ),
        UniqueConstraint(
            "id",
            "account_revision_id",
            "calendar_identity_id",
            "occurrence_key",
            name="uq_calendar_events_observation_owner",
        ),
        Index(
            "ix_calendar_events_identity_revision",
            "calendar_identity_id",
            "occurrence_key",
            "application_revision",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    calendar_identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    sync_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
    )
    provider_event_id: Mapped[str] = mapped_column(String(1024), nullable=False)
    recurring_series_id: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    occurrence_key: Mapped[str] = mapped_column(String(2200), nullable=False)
    original_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    original_start_instant: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provider_etag: Mapped[str] = mapped_column(String(1024), nullable=False)
    provider_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    application_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_instant: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_instant: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_timezone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    is_private: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
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


class CalendarEventObservation(Base):
    __tablename__ = "calendar_event_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["sync_run_id", "calendar_identity_id", "account_revision_id"],
            [
                "calendar_sync_runs.id",
                "calendar_sync_runs.calendar_identity_id",
                "calendar_sync_runs.account_revision_id",
            ],
            name="fk_calendar_observations_run_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "event_revision_id",
                "account_revision_id",
                "calendar_identity_id",
                "occurrence_key",
            ],
            [
                "calendar_event_revisions.id",
                "calendar_event_revisions.account_revision_id",
                "calendar_event_revisions.calendar_identity_id",
                "calendar_event_revisions.occurrence_key",
            ],
            name="fk_calendar_observations_event_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "sync_run_id",
            "occurrence_key",
            name="uq_calendar_observations_run_occurrence",
        ),
        Index(
            "ix_calendar_observations_lineage_occurrence",
            "account_revision_id",
            "calendar_identity_id",
            "occurrence_key",
            "sync_run_id",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sync_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    account_revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    calendar_identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    occurrence_key: Mapped[str] = mapped_column(String(2200), nullable=False)
    event_revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
