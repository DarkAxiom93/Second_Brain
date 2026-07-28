"""Add structured Memory metadata.

Revision ID: 0004_memory_metadata
Revises: 0003_sources
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_memory_metadata"
down_revision: str | None = "0003_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add structured metadata without changing existing API data."""

    op.add_column("memories", sa.Column("title", sa.String(255), nullable=True))
    op.add_column("memories", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column(
        "memories",
        sa.Column(
            "memory_type", sa.String(50), server_default="semantic", nullable=False
        ),
    )
    op.add_column(
        "memories",
        sa.Column("importance", sa.Float(), server_default="0.5", nullable=False),
    )
    op.add_column(
        "memories",
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
    )
    op.add_column(
        "memories",
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
    )
    op.add_column(
        "memories", sa.Column("event_time", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "memories", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "memories",
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_memories_memory_type",
        "memories",
        "memory_type IN ('working', 'episodic', 'semantic', 'decision', "
        "'procedural', 'preference', 'temporary')",
    )
    op.create_check_constraint(
        "ck_memories_importance_range",
        "memories",
        "importance >= 0.0 AND importance <= 1.0",
    )
    op.create_check_constraint(
        "ck_memories_confidence_range",
        "memories",
        "confidence >= 0.0 AND confidence <= 1.0",
    )
    op.create_check_constraint(
        "ck_memories_status",
        "memories",
        "status IN ('active', 'superseded', 'invalid', 'archived')",
    )
    op.create_foreign_key(
        "fk_memories_supersedes_id_memories",
        "memories",
        "memories",
        ["supersedes_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_memories_memory_type", "memories", ["memory_type"])
    op.create_index("ix_memories_status", "memories", ["status"])
    op.create_index("ix_memories_event_time", "memories", ["event_time"])
    op.create_index("ix_memories_supersedes_id", "memories", ["supersedes_id"])


def downgrade() -> None:
    """Remove only structured Memory metadata."""

    op.drop_index("ix_memories_supersedes_id", table_name="memories")
    op.drop_index("ix_memories_event_time", table_name="memories")
    op.drop_index("ix_memories_status", table_name="memories")
    op.drop_index("ix_memories_memory_type", table_name="memories")
    op.drop_constraint(
        "fk_memories_supersedes_id_memories", "memories", type_="foreignkey"
    )
    op.drop_constraint("ck_memories_status", "memories", type_="check")
    op.drop_constraint("ck_memories_confidence_range", "memories", type_="check")
    op.drop_constraint("ck_memories_importance_range", "memories", type_="check")
    op.drop_constraint("ck_memories_memory_type", "memories", type_="check")
    for column in (
        "supersedes_id",
        "expires_at",
        "event_time",
        "status",
        "confidence",
        "importance",
        "memory_type",
        "summary",
        "title",
    ):
        op.drop_column("memories", column)
