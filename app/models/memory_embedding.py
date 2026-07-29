"""Persistence model for the current semantic embedding of a Memory."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.memory import Memory


class MemoryEmbedding(Base):
    """One provider-produced embedding associated with one Memory."""

    __tablename__ = "memory_embeddings"
    __table_args__ = (
        UniqueConstraint("memory_id", name="uq_memory_embeddings_memory_id"),
        CheckConstraint("dimensions = 1536", name="ck_memory_embeddings_dimensions"),
        CheckConstraint(
            "input_hash ~ '^[0-9a-f]{64}$'",
            name="ck_memory_embeddings_input_hash_format",
        ),
        Index("ix_memory_embeddings_provider", "provider"),
        Index("ix_memory_embeddings_model", "model"),
        Index(
            "ix_memory_embeddings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    dimensions: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    input_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    embedded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
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

    memory: Mapped["Memory"] = relationship(back_populates="embedding_record")
