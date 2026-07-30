"""Allow Memories to be explicitly marked expired."""

from collections.abc import Sequence

from alembic import op

revision: str = "0009_memory_expiration"
down_revision: str | None = "0008_memory_proposals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_memories_status", "memories", type_="check")
    op.create_check_constraint(
        "ck_memories_status",
        "memories",
        "status IN ('active', 'superseded', 'invalid', 'archived', 'expired')",
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM memories WHERE status = 'expired') THEN
                RAISE EXCEPTION
                    'cannot downgrade memory expiration while expired memories exist';
            END IF;
        END
        $$
        """
    )
    op.drop_constraint("ck_memories_status", "memories", type_="check")
    op.create_check_constraint(
        "ck_memories_status",
        "memories",
        "status IN ('active', 'superseded', 'invalid', 'archived')",
    )
