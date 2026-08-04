"""Create the five Agent Runtime persistence tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import Base
from app.models import Project  # noqa: F401 - load all referenced model tables
from app.models.agent_runtime import (
    AgentEvent,
    AgentRun,
    AgentStep,
    ApprovalRequest,
    ToolInvocation,
)

revision: str = "0010_agent_runtime_persistence"
down_revision: str | None = "0009_memory_expiration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    AgentRun.__table__,
    AgentStep.__table__,
    ToolInvocation.__table__,
    ApprovalRequest.__table__,
    AgentEvent.__table__,
)


def upgrade() -> None:
    metadata = sa.MetaData()
    for source in Base.metadata.sorted_tables:
        source.to_metadata(metadata)
    for source in TABLES:
        table = metadata.tables[source.name]
        op.create_table(table.name, *table.columns, *table.constraints)
        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            op.create_index(
                index.name,
                table.name,
                [column.name for column in index.columns],
                unique=index.unique,
            )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table.name)
