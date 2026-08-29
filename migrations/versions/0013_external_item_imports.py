"""Add exact ExternalItem import provenance."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import Base
from app.models import ExternalItem, ExternalItemImport, SourceDocument  # noqa: F401

revision: str = "0013_external_item_imports"
down_revision: str | None = "0012_connector_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    metadata = sa.MetaData()
    for source in Base.metadata.sorted_tables:
        source.to_metadata(metadata)
    table = metadata.tables[ExternalItemImport.__tablename__]
    op.create_table(table.name, *table.columns, *table.constraints)


def downgrade() -> None:
    op.drop_table(ExternalItemImport.__tablename__)
