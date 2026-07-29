"""Auditable Memory proposal-extraction attempt persistence."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.memory_proposal import MemoryProposal
    from app.models.project import Project
    from app.models.source_document import SourceDocument


class MemoryExtractionRun(Base):
    """One deterministic proposal-extraction attempt for a document."""

    __tablename__ = "memory_extraction_runs"
    __table_args__ = (
        CheckConstraint(
            "input_hash ~ '^[0-9a-f]{64}$'",
            name="ck_memory_extraction_runs_input_hash_format",
        ),
        CheckConstraint(
            "run_status IN ('pending', 'completed', 'failed')",
            name="ck_memory_extraction_runs_run_status",
        ),
        UniqueConstraint(
            "document_id",
            "provider",
            "model",
            "prompt_version",
            "input_hash",
            name="uq_memory_extraction_runs_identity",
        ),
        Index("ix_memory_extraction_runs_document_id", "document_id"),
        Index("ix_memory_extraction_runs_project_id", "project_id"),
        Index("ix_memory_extraction_runs_run_status", "run_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    input_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    run_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
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

    document: Mapped["SourceDocument"] = relationship(back_populates="extraction_runs")
    project: Mapped["Project | None"] = relationship(back_populates="extraction_runs")
    proposals: Mapped[list["MemoryProposal"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="(MemoryProposal.proposal_index, MemoryProposal.id)",
    )
