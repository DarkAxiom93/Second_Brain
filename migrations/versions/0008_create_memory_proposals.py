"""Create reviewable Memory extraction runs and proposals."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_memory_proposals"
down_revision: str | None = "0007_source_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_extraction_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=False),
        sa.Column("input_hash", sa.CHAR(64), nullable=False),
        sa.Column(
            "run_status",
            sa.String(20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            "input_hash ~ '^[0-9a-f]{64}$'",
            name="ck_memory_extraction_runs_input_hash_format",
        ),
        sa.CheckConstraint(
            "run_status IN ('pending', 'completed', 'failed')",
            name="ck_memory_extraction_runs_run_status",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["source_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "provider",
            "model",
            "prompt_version",
            "input_hash",
            name="uq_memory_extraction_runs_identity",
        ),
    )
    for column in ("document_id", "project_id", "run_status"):
        op.create_index(
            f"ix_memory_extraction_runs_{column}", "memory_extraction_runs", [column]
        )
    op.create_table(
        "memory_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_chunk_hash", sa.CHAR(64), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("proposal_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("memory_type", sa.String(50), nullable=False),
        sa.Column(
            "importance", sa.Float(), server_default=sa.text("'0.5'"), nullable=False
        ),
        sa.Column(
            "confidence", sa.Float(), server_default=sa.text("'0.5'"), nullable=False
        ),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("evidence_char_start", sa.Integer(), nullable=False),
        sa.Column("evidence_char_end", sa.Integer(), nullable=False),
        sa.Column("source_locator", sa.String(255), nullable=True),
        sa.Column("proposal_hash", sa.CHAR(64), nullable=False),
        sa.Column(
            "review_status",
            sa.String(20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=True),
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
            "source_chunk_hash ~ '^[0-9a-f]{64}$'",
            name="ck_memory_proposals_source_chunk_hash_format",
        ),
        sa.CheckConstraint(
            "proposal_index >= 0", name="ck_memory_proposals_proposal_index_nonnegative"
        ),
        sa.CheckConstraint(
            "length(btrim(content, E' \\t\\n\\r\\f\\v')) > 0",
            name="ck_memory_proposals_content_nonblank",
        ),
        sa.CheckConstraint(
            "memory_type IN ('working', 'episodic', 'semantic', 'decision', "
            "'procedural', 'preference', 'temporary')",
            name="ck_memory_proposals_memory_type",
        ),
        sa.CheckConstraint(
            "importance >= 0.0 AND importance <= 1.0",
            name="ck_memory_proposals_importance_range",
        ),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_memory_proposals_confidence_range",
        ),
        sa.CheckConstraint(
            "length(btrim(evidence_text, E' \\t\\n\\r\\f\\v')) > 0",
            name="ck_memory_proposals_evidence_text_nonblank",
        ),
        sa.CheckConstraint(
            "evidence_char_start >= 0",
            name="ck_memory_proposals_evidence_char_start_nonnegative",
        ),
        sa.CheckConstraint(
            "evidence_char_end > evidence_char_start",
            name="ck_memory_proposals_evidence_char_end_after_start",
        ),
        sa.CheckConstraint(
            "proposal_hash ~ '^[0-9a-f]{64}$'",
            name="ck_memory_proposals_proposal_hash_format",
        ),
        sa.CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected')",
            name="ck_memory_proposals_review_status",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["memory_extraction_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_chunk_id"], ["source_chunks.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "source_chunk_id",
            "proposal_index",
            name="uq_memory_proposals_run_chunk_index",
        ),
        sa.UniqueConstraint(
            "run_id", "proposal_hash", name="uq_memory_proposals_run_hash"
        ),
        sa.UniqueConstraint("memory_id", name="uq_memory_proposals_memory_id"),
    )
    for column in ("run_id", "source_chunk_id", "project_id", "review_status"):
        op.create_index(f"ix_memory_proposals_{column}", "memory_proposals", [column])


def downgrade() -> None:
    op.drop_table("memory_proposals")
    op.drop_table("memory_extraction_runs")
