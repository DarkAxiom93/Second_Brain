"""Add PostgreSQL full-text search for Memories.

Revision ID: 0005_memory_search
Revises: 0004_memory_metadata
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_memory_search"
down_revision: str | None = "0004_memory_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEARCH_VECTOR_EXPRESSION = (
    "setweight(to_tsvector('simple', coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('simple', coalesce(summary, '')), 'B') || "
    "setweight(to_tsvector('simple', coalesce(content, '')), 'C') || "
    "setweight(to_tsvector('simple', coalesce(source, '')), 'D')"
)


def upgrade() -> None:
    """Add the generated search vector and its GIN index."""

    op.add_column(
        "memories",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(SEARCH_VECTOR_EXPRESSION, persisted=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_memories_search_vector",
        "memories",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Remove only the search index and generated column."""

    op.drop_index("ix_memories_search_vector", table_name="memories")
    op.drop_column("memories", "search_vector")
