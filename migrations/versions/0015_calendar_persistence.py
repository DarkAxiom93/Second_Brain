"""Add inert provider-specific Google Calendar persistence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import Base

revision: str = "0015_calendar_persistence"
down_revision: str | None = "0014_connector_refresh_schedules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    metadata = sa.MetaData()
    for source in Base.metadata.sorted_tables:
        source.to_metadata(metadata)
    for name in (
        "calendar_account_revisions",
        "calendar_identities",
        "calendar_sync_runs",
        "calendar_event_revisions",
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
    op.drop_table("calendar_event_revisions")
    op.drop_table("calendar_sync_runs")
    op.drop_table("calendar_identities")
    op.drop_table("calendar_account_revisions")
