"""Immutable provenance for one explicit ExternalItem import."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.connector import ExternalItem
    from app.models.source_document import SourceDocument


class ExternalItemImport(Base):
    """Exact ExternalItem revision to audited local document relationship."""

    __tablename__ = "external_item_imports"
    __table_args__ = (
        CheckConstraint(
            "confirmation_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_external_item_imports_confirmation_fingerprint",
        ),
        CheckConstraint(
            "canonical_source_url IS NULL OR "
            "(char_length(canonical_source_url) BETWEEN 19 AND 500 AND "
            "canonical_source_url ~ '^https://github[.]com/[A-Za-z0-9_.-]+/"
            "[A-Za-z0-9_.-]+(/issues/[1-9][0-9]*|/pull/[1-9][0-9]*)?$')",
            name="ck_external_item_imports_canonical_source_url",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_items.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    confirmation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    external_item: Mapped["ExternalItem"] = relationship()
    source_document: Mapped["SourceDocument"] = relationship()
