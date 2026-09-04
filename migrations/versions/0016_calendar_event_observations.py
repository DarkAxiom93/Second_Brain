"""Add deterministic Calendar run-occurrence observation evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_calendar_event_observations"
down_revision: str | None = "0015_calendar_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    sync_columns = {
        value["name"] for value in inspector.get_columns("calendar_sync_runs")
    }
    if "observation_evidence_version" not in sync_columns:
        op.add_column(
            "calendar_sync_runs",
            sa.Column("observation_evidence_version", sa.String(32), nullable=True),
        )
    sync_checks = {
        value["name"] for value in inspector.get_check_constraints("calendar_sync_runs")
    }
    if "ck_calendar_sync_observation_evidence_version" not in sync_checks:
        op.create_check_constraint(
            "ck_calendar_sync_observation_evidence_version",
            "calendar_sync_runs",
            "observation_evidence_version IS NULL OR "
            "observation_evidence_version = 'calendar-observations-v1'",
        )
    event_uniques = {
        value["name"]
        for value in inspector.get_unique_constraints("calendar_event_revisions")
    }
    if "uq_calendar_events_observation_owner" not in event_uniques:
        op.create_unique_constraint(
            "uq_calendar_events_observation_owner",
            "calendar_event_revisions",
            ["id", "account_revision_id", "calendar_identity_id", "occurrence_key"],
        )
    op.create_table(
        "calendar_event_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sync_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "calendar_identity_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("occurrence_key", sa.String(2200), nullable=False),
        sa.Column("event_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["sync_run_id", "calendar_identity_id", "account_revision_id"],
            [
                "calendar_sync_runs.id",
                "calendar_sync_runs.calendar_identity_id",
                "calendar_sync_runs.account_revision_id",
            ],
            name="fk_calendar_observations_run_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "event_revision_id",
                "account_revision_id",
                "calendar_identity_id",
                "occurrence_key",
            ],
            [
                "calendar_event_revisions.id",
                "calendar_event_revisions.account_revision_id",
                "calendar_event_revisions.calendar_identity_id",
                "calendar_event_revisions.occurrence_key",
            ],
            name="fk_calendar_observations_event_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_calendar_event_observations"),
        sa.UniqueConstraint(
            "sync_run_id",
            "occurrence_key",
            name="uq_calendar_observations_run_occurrence",
        ),
    )
    op.create_index(
        "ix_calendar_observations_lineage_occurrence",
        "calendar_event_observations",
        [
            "account_revision_id",
            "calendar_identity_id",
            "occurrence_key",
            "sync_run_id",
        ],
    )


def downgrade() -> None:
    op.drop_table("calendar_event_observations")
    op.drop_constraint(
        "uq_calendar_events_observation_owner",
        "calendar_event_revisions",
        type_="unique",
    )
    op.drop_constraint(
        "ck_calendar_sync_observation_evidence_version",
        "calendar_sync_runs",
        type_="check",
    )
    op.drop_column("calendar_sync_runs", "observation_evidence_version")
