"""Explicit operator-started one-tick trigger-only Automation scheduler."""

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.agent_runs.service import AgentRunCapacityError
from app.automations import scheduler
from app.core.config import get_settings
from app.db.session import get_engine


def _verify_operator_database() -> None:
    engine = get_engine()
    url = make_url(str(engine.url))
    if url.host != "127.0.0.1" or url.database != "second_brain":
        raise SystemExit("scheduler requires the verified development database")
    with engine.connect() as connection:
        if connection.scalar(text("SELECT current_database()")) != "second_brain":
            raise SystemExit("scheduler database identity mismatch")


def run_one_tick(*, now: datetime | None = None) -> scheduler.TickResult:
    """Run one bounded tick with a single authoritative UTC instant."""

    operation_time = (now or datetime.now(UTC)).astimezone(UTC)
    settings = get_settings()
    limit = settings.automation_scheduler_batch_size
    lease = timedelta(seconds=settings.automation_lease_seconds)
    owner = uuid.uuid4()
    with Session(get_engine()) as session:
        materialized = scheduler.materialize_due(
            session, now=operation_time, limit=limit
        )
        session.commit()
        claims = scheduler.claim_due(
            session,
            now=operation_time,
            owner_token=owner,
            lease_duration=lease,
            limit=limit,
        )
        session.commit()
        linked: list[uuid.UUID] = []
        deferred: list[uuid.UUID] = []
        for claim in claims:
            try:
                run_id, _ = scheduler.create_and_link_run(
                    session, claim, now=operation_time
                )
                session.commit()
                linked.append(run_id)
            except AgentRunCapacityError:
                session.rollback()
                deferred.append(claim.occurrence_id)
        return scheduler.TickResult(
            materialized_ids=tuple(item.id for item in materialized),
            claimed_ids=tuple(item.occurrence_id for item in claims),
            linked_run_ids=tuple(linked),
            capacity_deferred_ids=tuple(deferred),
        )


def main() -> int:
    try:
        _verify_operator_database()
        result = run_one_tick()
        print(
            json.dumps(
                {
                    "materialized": len(result.materialized_ids),
                    "claimed": len(result.claimed_ids),
                    "runs_created_or_linked": len(result.linked_run_ids),
                    "capacity_deferred": len(result.capacity_deferred_ids),
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception:
        print(json.dumps({"error": "scheduler_unavailable"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
