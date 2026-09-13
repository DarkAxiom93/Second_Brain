"""Local Capture persistence model."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_LOWER_HEX_64 = "~ '^[0-9a-f]{64}$'"


class CaptureItem(Base):
    """An inert, normalized note awaiting explicit triage."""

    __tablename__ = "capture_items"
    __table_args__ = (
        CheckConstraint(
            "state IN ('pending', 'processed', 'discarded')",
            name="ck_capture_items_state",
        ),
        CheckConstraint("revision > 0", name="ck_capture_items_positive_revision"),
        CheckConstraint(
            "(state = 'processed' AND processed_at IS NOT NULL AND "
            "resulting_source_id IS NOT NULL) OR "
            "(state <> 'processed' AND processed_at IS NULL AND "
            "resulting_source_id IS NULL)",
            name="ck_capture_items_processing_fields",
        ),
        CheckConstraint(
            f"idempotency_key_hash {_LOWER_HEX_64}",
            name="ck_capture_items_idempotency_hash",
        ),
        CheckConstraint(
            f"request_fingerprint {_LOWER_HEX_64}",
            name="ck_capture_items_request_fingerprint",
        ),
        CheckConstraint(
            "char_length(content) BETWEEN 1 AND 8000 AND "
            "octet_length(content) <= 32000",
            name="ck_capture_items_content_bounds",
        ),
        UniqueConstraint(
            "idempotency_key_hash", name="uq_capture_items_idempotency_hash"
        ),
        UniqueConstraint(
            "resulting_source_id", name="uq_capture_items_resulting_source_id"
        ),
        Index(
            "ix_capture_items_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
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
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resulting_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=True,
    )
    idempotency_key_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', coalesce(content, ''))", persisted=True),
        nullable=False,
    )


Index(
    "ix_capture_items_scope_state_browse",
    CaptureItem.project_id,
    CaptureItem.state,
    CaptureItem.created_at.desc(),
    CaptureItem.id.desc(),
)
