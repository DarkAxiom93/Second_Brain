"""Durable, safe persistence models for the future Agent Runtime."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

HASH_CHECK = "~ '^[0-9a-f]{64}$'"


class AgentRun(Base):
    """One durable, bounded Agent attempt; no runtime behavior lives here."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('created','planning','ready','running','awaiting_approval',"
            "'completed','failed','cancelled','expired')",
            name="ck_agent_runs_state",
        ),
        CheckConstraint("revision >= 0", name="ck_agent_runs_revision_nonnegative"),
        CheckConstraint(
            "step_budget >= 0 AND tool_call_budget >= 0 AND retry_budget >= 0",
            name="ck_agent_runs_budgets_nonnegative",
        ),
        CheckConstraint(
            "planning_deadline <= run_deadline", name="ck_agent_runs_deadline_order"
        ),
        CheckConstraint(
            "started_at IS NULL OR started_at >= created_at",
            name="ck_agent_runs_started_order",
        ),
        CheckConstraint(
            "finished_at IS NULL OR (started_at IS NOT NULL AND "
            "finished_at >= started_at)",
            name="ck_agent_runs_finished_order",
        ),
        CheckConstraint(
            "(state IN ('completed','failed','cancelled','expired')) = "
            "(finished_at IS NOT NULL)",
            name="ck_agent_runs_terminal_finished",
        ),
        CheckConstraint(
            f"idempotency_key_hash {HASH_CHECK}", name="ck_agent_runs_idempotency_hash"
        ),
        CheckConstraint(
            f"normalized_request_fingerprint {HASH_CHECK}",
            name="ck_agent_runs_request_fingerprint",
        ),
        UniqueConstraint("idempotency_key_hash", name="uq_agent_runs_idempotency_hash"),
        UniqueConstraint("id", "project_id", name="uq_agent_runs_id_project"),
        Index("ix_agent_runs_state_deadline", "state", "run_deadline"),
        Index("ix_agent_runs_project_created", "project_id", "created_at"),
        Index("ix_agent_runs_correlation_id", "correlation_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
    )
    agent_kind: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(50), nullable=False)
    goal_summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    registry_version: Mapped[str] = mapped_column(String(50), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="created", server_default="created"
    )
    step_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_call_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    retry_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    planning_deadline: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    run_deadline: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    correlation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    idempotency_key_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    normalized_request_fingerprint: Mapped[str] = mapped_column(
        CHAR(64), nullable=False
    )
    safe_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    steps: Mapped[list["AgentStep"]] = relationship(
        back_populates="run", passive_deletes=True, order_by="AgentStep.ordinal"
    )


class AgentStep(Base):
    """One immutable ordered plan unit and its bounded status fields."""

    __tablename__ = "agent_steps"
    __table_args__ = (
        CheckConstraint("ordinal >= 0", name="ck_agent_steps_ordinal_nonnegative"),
        CheckConstraint(
            "status IN ('pending','running','succeeded','failed','skipped',"
            "'cancelled')",
            name="ck_agent_steps_status",
        ),
        CheckConstraint(
            "octet_length(normalized_input::text) <= 65536",
            name="ck_agent_steps_input_size",
        ),
        CheckConstraint(
            "octet_length(expected_evidence::text) <= 16384",
            name="ck_agent_steps_evidence_size",
        ),
        CheckConstraint(
            "(tool_name IS NULL) = (tool_version IS NULL)",
            name="ck_agent_steps_tool_identity",
        ),
        CheckConstraint(
            "started_at IS NULL OR started_at >= created_at",
            name="ck_agent_steps_started_order",
        ),
        CheckConstraint(
            "finished_at IS NULL OR (started_at IS NOT NULL AND "
            "finished_at >= started_at)",
            name="ck_agent_steps_finished_order",
        ),
        UniqueConstraint("run_id", "ordinal", name="uq_agent_steps_run_ordinal"),
        UniqueConstraint("id", "run_id", name="uq_agent_steps_id_run"),
        Index("ix_agent_steps_status", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    purpose: Mapped[str] = mapped_column(String(1000), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tool_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    normalized_input: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    expected_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    success_condition: Mapped[str] = mapped_column(String(1000), nullable=False)
    stop_condition: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    run: Mapped[AgentRun] = relationship(back_populates="steps")


class ToolInvocation(Base):
    """One reserved attempt for one exact registered tool identity."""

    __tablename__ = "tool_invocations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["step_id", "run_id"],
            ["agent_steps.id", "agent_steps.run_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("attempt >= 0", name="ck_tool_invocations_attempt_nonnegative"),
        CheckConstraint(
            "authority IN ('read','propose','execute')",
            name="ck_tool_invocations_authority",
        ),
        CheckConstraint(
            "status IN ('reserved','running','succeeded','failed','timed_out',"
            "'cancelled','discarded')",
            name="ck_tool_invocations_status",
        ),
        CheckConstraint(
            f"validated_input_hash {HASH_CHECK}", name="ck_tool_invocations_input_hash"
        ),
        CheckConstraint(
            f"idempotency_key_hash {HASH_CHECK}",
            name="ck_tool_invocations_idempotency_hash",
        ),
        CheckConstraint(
            "octet_length(validated_input::text) <= 65536",
            name="ck_tool_invocations_input_size",
        ),
        CheckConstraint(
            "octet_length(evidence_references::text) <= 16384",
            name="ck_tool_invocations_evidence_size",
        ),
        CheckConstraint(
            "started_at IS NULL OR started_at >= reserved_at",
            name="ck_tool_invocations_started_order",
        ),
        CheckConstraint(
            "finished_at IS NULL OR (started_at IS NOT NULL AND "
            "finished_at >= started_at)",
            name="ck_tool_invocations_finished_order",
        ),
        UniqueConstraint("step_id", "attempt", name="uq_tool_invocations_step_attempt"),
        UniqueConstraint(
            "tool_name",
            "tool_version",
            "idempotency_key_hash",
            name="uq_tool_invocations_tool_idempotency",
        ),
        UniqueConstraint("id", "run_id", name="uq_tool_invocations_id_run"),
        Index("ix_tool_invocations_status_started", "status", "started_at"),
        Index("ix_tool_invocations_run_id", "run_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tool_version: Mapped[str] = mapped_column(String(50), nullable=False)
    authority: Mapped[str] = mapped_column(String(10), nullable=False)
    validated_input_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    validated_input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="reserved", server_default="reserved"
    )
    safe_result_summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    evidence_references: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    safe_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ApprovalRequest(Base):
    """An immutable exact proposal foundation; no execution semantics."""

    __tablename__ = "approval_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["step_id", "run_id"],
            ["agent_steps.id", "agent_steps.run_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('pending','approved','rejected','expired','superseded')",
            name="ck_approval_requests_status",
        ),
        CheckConstraint(
            f"proposal_hash {HASH_CHECK}", name="ck_approval_requests_proposal_hash"
        ),
        CheckConstraint(
            "expires_at > created_at", name="ck_approval_requests_expiration_order"
        ),
        CheckConstraint(
            "reviewed_at IS NULL OR reviewed_at >= created_at",
            name="ck_approval_requests_reviewed_order",
        ),
        CheckConstraint(
            "octet_length(normalized_input::text) <= 65536",
            name="ck_approval_requests_input_size",
        ),
        CheckConstraint(
            "octet_length(evidence_references::text) <= 16384",
            name="ck_approval_requests_evidence_size",
        ),
        UniqueConstraint(
            "execution_identity", name="uq_approval_requests_execution_identity"
        ),
        UniqueConstraint(
            "run_id",
            "step_id",
            "action_type",
            "target_type",
            "target_public_id",
            "target_version",
            "proposal_hash",
            name="uq_approval_requests_exact_proposal",
        ),
        UniqueConstraint("id", "run_id", name="uq_approval_requests_id_run"),
        Index("ix_approval_requests_status_expiry", "status", "expires_at"),
        Index("ix_approval_requests_run_created", "run_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    target_version: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    proposal_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    preview: Mapped[str] = mapped_column(String(2000), nullable=False)
    evidence_references: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    risk_classification: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewer_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    execution_identity: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )


class AgentEvent(Base):
    """Append-oriented allowlisted audit fact."""

    __tablename__ = "agent_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["step_id", "run_id"],
            ["agent_steps.id", "agent_steps.run_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["invocation_id", "run_id"],
            ["tool_invocations.id", "tool_invocations.run_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["approval_id", "run_id"],
            ["approval_requests.id", "approval_requests.run_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("sequence >= 0", name="ck_agent_events_sequence_nonnegative"),
        CheckConstraint("event_version >= 1", name="ck_agent_events_version_positive"),
        CheckConstraint(
            "octet_length(metadata::text) <= 4096", name="ck_agent_events_metadata_size"
        ),
        CheckConstraint(
            "recorded_at >= occurred_at", name="ck_agent_events_recorded_order"
        ),
        CheckConstraint(
            f"event_idempotency_hash IS NULL OR event_idempotency_hash {HASH_CHECK}",
            name="ck_agent_events_idempotency_hash",
        ),
        UniqueConstraint("run_id", "sequence", name="uq_agent_events_run_sequence"),
        UniqueConstraint(
            "run_id", "event_idempotency_hash", name="uq_agent_events_run_idempotency"
        ),
        Index("ix_agent_events_run_sequence", "run_id", "sequence"),
        Index("ix_agent_events_type_occurred", "event_type", "occurred_at"),
        Index("ix_agent_events_correlation_id", "correlation_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    invocation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    approval_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    safe_code: Mapped[str] = mapped_column(String(100), nullable=False)
    safe_message: Mapped[str] = mapped_column(String(1000), nullable=False)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    correlation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )
    event_idempotency_hash: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
