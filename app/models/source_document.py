"""Document metadata optionally associated with a Source."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.memory_extraction_run import MemoryExtractionRun
    from app.models.source import Source
    from app.models.source_chunk import SourceChunk


class SourceDocument(Base):
    """Persistence metadata for a Source that represents a document."""

    __tablename__ = "source_documents"
    __table_args__ = (
        CheckConstraint(
            "byte_size >= 0", name="ck_source_documents_byte_size_nonnegative"
        ),
        CheckConstraint(
            "ingestion_status IN ('pending', 'extracted', 'failed')",
            name="ck_source_documents_ingestion_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingestion_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    extracted_at: Mapped[datetime | None] = mapped_column(
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

    source: Mapped["Source"] = relationship(back_populates="document_record")
    chunks: Mapped[list["SourceChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="SourceChunk.chunk_index",
        passive_deletes=True,
    )
    extraction_runs: Mapped[list["MemoryExtractionRun"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
