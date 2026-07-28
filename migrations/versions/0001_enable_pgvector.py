"""Enable the pgvector extension.

Revision ID: 0001_enable_pgvector
Revises: None
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_enable_pgvector"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable pgvector without creating application tables."""

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Remove pgvector when explicitly run against a verified test database."""

    op.execute("DROP EXTENSION IF EXISTS vector")
