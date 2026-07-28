"""Create normalized sources and memory-source links.

Revision ID: 0003_sources
Revises: 0002_projects_memories
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_sources"
down_revision: str | None = "0002_projects_memories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create normalized sources and their memory links."""

    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sources_checksum", "sources", ["checksum"])
    op.create_index("ix_sources_created_at", "sources", ["created_at"])
    op.create_index("ix_sources_source_type", "sources", ["source_type"])

    op.create_table(
        "memory_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_location", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("memory_id", "source_id", name="uq_memory_sources_pair"),
    )
    op.create_index("ix_memory_sources_memory_id", "memory_sources", ["memory_id"])
    op.create_index("ix_memory_sources_source_id", "memory_sources", ["source_id"])


def downgrade() -> None:
    """Remove only normalized sources and their memory links."""

    op.drop_index("ix_memory_sources_source_id", table_name="memory_sources")
    op.drop_index("ix_memory_sources_memory_id", table_name="memory_sources")
    op.drop_table("memory_sources")
    op.drop_index("ix_sources_source_type", table_name="sources")
    op.drop_index("ix_sources_created_at", table_name="sources")
    op.drop_index("ix_sources_checksum", table_name="sources")
    op.drop_table("sources")
