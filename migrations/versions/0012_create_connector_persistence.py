"""Create the three inert connector persistence tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import Base
from app.models import Project  # noqa: F401 - referenced table
from app.models.connector import ConnectorAccount, ConnectorSyncRun, ExternalItem

revision: str = "0012_connector_persistence"
down_revision: str | None = "0011_automation_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    ConnectorAccount.__table__,
    ConnectorSyncRun.__table__,
    ExternalItem.__table__,
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
                postgresql_where=index.dialect_options["postgresql"].get("where"),
            )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table.name)
