"""Ordered text chunk persistence for Source documents."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
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
    from app.models.source_document import SourceDocument


class SourceChunk(Base):
    """An exact, ordered character range from a persisted document text."""

    __tablename__ = "source_chunks"
    __table_args__ = (
        CheckConstraint(
            "chunk_index >= 0", name="ck_source_chunks_chunk_index_nonnegative"
        ),
        CheckConstraint(
            "length(btrim(content, E' \\t\\n\\r\\f\\v')) > 0",
            name="ck_source_chunks_content_nonblank",
        ),
        CheckConstraint(
            "char_start >= 0", name="ck_source_chunks_char_start_nonnegative"
        ),
        CheckConstraint(
            "char_end > char_start", name="ck_source_chunks_char_end_after_start"
        ),
        CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_source_chunks_content_hash_format",
        ),
        UniqueConstraint(
            "document_id", "chunk_index", name="uq_source_chunks_document_chunk_index"
        ),
        Index("ix_source_chunks_document_id", "document_id"),
        Index("ix_source_chunks_content_hash", "content_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    document: Mapped["SourceDocument"] = relationship(back_populates="chunks")
