"""Create one current embedding record per Memory.

Revision ID: 0006_memory_embeddings
Revises: 0005_memory_search
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_memory_embeddings"
down_revision: str | None = "0005_memory_search"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create embedding persistence without backfilling existing Memories."""

    op.create_table(
        "memory_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("dimensions", sa.SmallInteger(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=False),
        sa.Column("input_hash", sa.CHAR(length=64), nullable=False),
        sa.Column(
            "embedded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        sa.CheckConstraint("dimensions = 1536", name="ck_memory_embeddings_dimensions"),
        sa.CheckConstraint(
            "input_hash ~ '^[0-9a-f]{64}$'",
            name="ck_memory_embeddings_input_hash_format",
        ),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("memory_id", name="uq_memory_embeddings_memory_id"),
    )
    op.create_index("ix_memory_embeddings_provider", "memory_embeddings", ["provider"])
    op.create_index("ix_memory_embeddings_model", "memory_embeddings", ["model"])
    op.create_index(
        "ix_memory_embeddings_embedding_hnsw",
        "memory_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    """Drop only embedding persistence and leave pgvector installed."""

    op.drop_index("ix_memory_embeddings_embedding_hnsw", table_name="memory_embeddings")
    op.drop_index("ix_memory_embeddings_model", table_name="memory_embeddings")
    op.drop_index("ix_memory_embeddings_provider", table_name="memory_embeddings")
    op.drop_table("memory_embeddings")
