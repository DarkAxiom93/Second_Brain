"""Create Source document metadata and ordered text chunks.

Revision ID: 0007_source_documents
Revises: 0006_memory_embeddings
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_source_documents"
down_revision: str | None = "0006_memory_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add document persistence without backfilling existing Sources."""

    op.create_table(
        "source_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column(
            "ingestion_status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "byte_size >= 0", name="ck_source_documents_byte_size_nonnegative"
        ),
        sa.CheckConstraint(
            "ingestion_status IN ('pending', 'extracted', 'failed')",
            name="ck_source_documents_ingestion_status",
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", name="uq_source_documents_source_id"),
    )
    op.create_table(
        "source_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("locator", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "chunk_index >= 0", name="ck_source_chunks_chunk_index_nonnegative"
        ),
        sa.CheckConstraint(
            "length(btrim(content, E' \\t\\n\\r\\f\\v')) > 0",
            name="ck_source_chunks_content_nonblank",
        ),
        sa.CheckConstraint(
            "char_start >= 0", name="ck_source_chunks_char_start_nonnegative"
        ),
        sa.CheckConstraint(
            "char_end > char_start", name="ck_source_chunks_char_end_after_start"
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_source_chunks_content_hash_format",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["source_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name="uq_source_chunks_document_chunk_index"
        ),
    )
    op.create_index("ix_source_chunks_document_id", "source_chunks", ["document_id"])
    op.create_index("ix_source_chunks_content_hash", "source_chunks", ["content_hash"])


def downgrade() -> None:
    """Remove only document and chunk persistence."""

    op.drop_index("ix_source_chunks_content_hash", table_name="source_chunks")
    op.drop_index("ix_source_chunks_document_id", table_name="source_chunks")
    op.drop_table("source_chunks")
    op.drop_table("source_documents")
