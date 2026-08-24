"""Create the three inert Automation persistence tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import Base
from app.models import AgentRun, Project  # noqa: F401 - referenced tables
from app.models.automation import (
    Automation,
    AutomationNotification,
    AutomationOccurrence,
)

revision: str = "0011_automation_persistence"
down_revision: str | None = "0010_agent_runtime_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    Automation.__table__,
    AutomationOccurrence.__table__,
    AutomationNotification.__table__,
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
