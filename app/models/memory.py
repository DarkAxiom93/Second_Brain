"""Memory persistence model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.memory_embedding import MemoryEmbedding
    from app.models.memory_proposal import MemoryProposal
    from app.models.memory_source import MemorySource
    from app.models.project import Project


class Memory(Base):
    """A persisted memory optionally associated with a project."""

    __tablename__ = "memories"
    __table_args__ = (
        CheckConstraint(
            "memory_type IN ('working', 'episodic', 'semantic', 'decision', "
            "'procedural', 'preference', 'temporary')",
            name="ck_memories_memory_type",
        ),
        CheckConstraint(
            "importance >= 0.0 AND importance <= 1.0",
            name="ck_memories_importance_range",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_memories_confidence_range",
        ),
        CheckConstraint(
            "status IN ('active', 'superseded', 'invalid', 'archived')",
            name="ck_memories_status",
        ),
        Index("ix_memories_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    memory_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="semantic",
        server_default="semantic",
        index=True,
    )
    importance: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5, server_default="0.5"
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, server_default="1.0"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )
    event_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('simple', coalesce(title, '')), 'A') || "
            "setweight(to_tsvector('simple', coalesce(summary, '')), 'B') || "
            "setweight(to_tsvector('simple', coalesce(content, '')), 'C') || "
            "setweight(to_tsvector('simple', coalesce(source, '')), 'D')",
            persisted=True,
        ),
        nullable=False,
    )

    project: Mapped["Project | None"] = relationship(back_populates="memories")
    source_links: Mapped[list["MemorySource"]] = relationship(
        back_populates="memory",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    embedding_record: Mapped["MemoryEmbedding | None"] = relationship(
        back_populates="memory",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
        single_parent=True,
    )
    proposal_record: Mapped["MemoryProposal | None"] = relationship(
        back_populates="memory", passive_deletes=True, uselist=False
    )
