"""Add the inert Local V1.7 Capture persistence foundation."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_capture_items"
down_revision: str | None = "0016_calendar_event_observations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "capture_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("state", sa.String(20), server_default="pending", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resulting_source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key_hash", sa.CHAR(64), nullable=False),
        sa.Column("request_fingerprint", sa.CHAR(64), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', coalesce(content, ''))", persisted=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'processed', 'discarded')",
            name="ck_capture_items_state",
        ),
        sa.CheckConstraint("revision > 0", name="ck_capture_items_positive_revision"),
        sa.CheckConstraint(
            "(state = 'processed' AND processed_at IS NOT NULL AND "
            "resulting_source_id IS NOT NULL) OR "
            "(state <> 'processed' AND processed_at IS NULL AND "
            "resulting_source_id IS NULL)",
            name="ck_capture_items_processing_fields",
        ),
        sa.CheckConstraint(
            "idempotency_key_hash ~ '^[0-9a-f]{64}$'",
            name="ck_capture_items_idempotency_hash",
        ),
        sa.CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_capture_items_request_fingerprint",
        ),
        sa.CheckConstraint(
            "char_length(content) BETWEEN 1 AND 8000 AND "
            "octet_length(content) <= 32000",
            name="ck_capture_items_content_bounds",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["resulting_source_id"], ["sources.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key_hash", name="uq_capture_items_idempotency_hash"
        ),
        sa.UniqueConstraint(
            "resulting_source_id", name="uq_capture_items_resulting_source_id"
        ),
    )
    op.create_index(
        "ix_capture_items_scope_state_browse",
        "capture_items",
        ["project_id", "state", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_capture_items_search_vector",
        "capture_items",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_capture_items_search_vector", table_name="capture_items")
    op.drop_index("ix_capture_items_scope_state_browse", table_name="capture_items")
    op.drop_table("capture_items")
