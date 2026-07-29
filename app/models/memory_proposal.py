"""Reviewable proposed Memory persistence."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.memory import Memory
    from app.models.memory_extraction_run import MemoryExtractionRun
    from app.models.project import Project
    from app.models.source_chunk import SourceChunk


class MemoryProposal(Base):
    """A reviewable Memory candidate supported by immutable evidence."""

    __tablename__ = "memory_proposals"
    __table_args__ = (
        CheckConstraint(
            "source_chunk_hash ~ '^[0-9a-f]{64}$'",
            name="ck_memory_proposals_source_chunk_hash_format",
        ),
        CheckConstraint(
            "proposal_index >= 0", name="ck_memory_proposals_proposal_index_nonnegative"
        ),
        CheckConstraint(
            "length(btrim(content, E' \\t\\n\\r\\f\\v')) > 0",
            name="ck_memory_proposals_content_nonblank",
        ),
        CheckConstraint(
            "memory_type IN ('working', 'episodic', 'semantic', 'decision', "
            "'procedural', 'preference', 'temporary')",
            name="ck_memory_proposals_memory_type",
        ),
        CheckConstraint(
            "importance >= 0.0 AND importance <= 1.0",
            name="ck_memory_proposals_importance_range",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_memory_proposals_confidence_range",
        ),
        CheckConstraint(
            "length(btrim(evidence_text, E' \\t\\n\\r\\f\\v')) > 0",
            name="ck_memory_proposals_evidence_text_nonblank",
        ),
        CheckConstraint(
            "evidence_char_start >= 0",
            name="ck_memory_proposals_evidence_char_start_nonnegative",
        ),
        CheckConstraint(
            "evidence_char_end > evidence_char_start",
            name="ck_memory_proposals_evidence_char_end_after_start",
        ),
        CheckConstraint(
            "proposal_hash ~ '^[0-9a-f]{64}$'",
            name="ck_memory_proposals_proposal_hash_format",
        ),
        CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected')",
            name="ck_memory_proposals_review_status",
        ),
        UniqueConstraint(
            "run_id",
            "source_chunk_id",
            "proposal_index",
            name="uq_memory_proposals_run_chunk_index",
        ),
        UniqueConstraint(
            "run_id", "proposal_hash", name="uq_memory_proposals_run_hash"
        ),
        UniqueConstraint("memory_id", name="uq_memory_proposals_memory_id"),
        Index("ix_memory_proposals_run_id", "run_id"),
        Index("ix_memory_proposals_source_chunk_id", "source_chunk_id"),
        Index("ix_memory_proposals_project_id", "project_id"),
        Index("ix_memory_proposals_review_status", "review_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memory_extraction_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_chunks.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_chunk_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    proposal_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    importance: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5, server_default="0.5"
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5, server_default="0.5"
    )
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    source_locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    proposal_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    memory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="SET NULL"),
        nullable=True,
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

    run: Mapped["MemoryExtractionRun"] = relationship(back_populates="proposals")
    source_chunk: Mapped["SourceChunk | None"] = relationship(
        back_populates="memory_proposals"
    )
    project: Mapped["Project | None"] = relationship(back_populates="memory_proposals")
    memory: Mapped["Memory | None"] = relationship(back_populates="proposal_record")
