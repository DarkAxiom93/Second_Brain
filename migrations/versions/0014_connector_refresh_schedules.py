"""Add connector-owned refresh scheduling persistence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import Base

revision: str = "0014_connector_refresh_schedules"
down_revision: str | None = "0013_external_item_imports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    metadata = sa.MetaData()
    for source in Base.metadata.sorted_tables:
        source.to_metadata(metadata)
    for name in (
        "connector_refresh_schedules",
        "connector_refresh_occurrences",
        "connector_refresh_notifications",
    ):
        table = metadata.tables[name]
        op.create_table(table.name, *table.columns, *table.constraints)
        for index in table.indexes:
            op.create_index(
                index.name,
                table.name,
                [column.name for column in index.columns],
                unique=index.unique,
                postgresql_where=index.dialect_options["postgresql"].get("where"),
            )


def downgrade() -> None:
    op.drop_table("connector_refresh_notifications")
    op.drop_table("connector_refresh_occurrences")
    op.drop_table("connector_refresh_schedules")
