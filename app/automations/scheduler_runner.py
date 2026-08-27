"""Explicit operator-started one-tick trigger-only Automation scheduler."""

import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.agent_planning.dependencies import (
    configured_embedding_provider_available,
    get_planning_provider,
)
from app.agent_runs.service import AgentRunCapacityError
from app.automations import coordinator, scheduler
from app.automations.catalog import get_automatic_agent_definition
from app.core.config import get_settings
from app.daily_brief.dependencies import get_daily_brief_provider
from app.db.session import get_engine
from app.embeddings.dependencies import get_embedding_provider
from app.repositories import automations as repository


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

    settings = get_settings()
    limit = settings.automation_scheduler_batch_size
    lease = timedelta(seconds=settings.automation_lease_seconds)
    owner = uuid.uuid4()
    with Session(get_engine()) as session:
        database_time = repository.database_utc_now(session)
        operation_time = scheduler._aware_utc(now) if now is not None else database_time
        reconciled = scheduler.reconcile_linked(
            session, now=operation_time, limit=limit
        )
        session.commit()
        reclaimed = scheduler.reclaim_expired(
            session,
            now=operation_time,
            owner_token=owner,
            lease_duration=lease,
            limit=limit,
        )
        session.commit()
        materialized = scheduler.materialize_due(
            session, now=operation_time, limit=limit
        )
        materialized_ids = tuple(item.id for item in materialized)
        missed_ids = tuple(item.id for item in materialized if item.state == "missed")
        session.commit()
        claims = scheduler.claim_due(
            session,
            now=operation_time,
            owner_token=owner,
            lease_duration=lease,
            limit=limit,
        )
        session.commit()
        all_claims = list(reclaimed)
        known = {item.occurrence_id for item in all_claims}
        all_claims.extend(item for item in claims if item.occurrence_id not in known)
        linked: list[uuid.UUID] = []
        deferred: list[uuid.UUID] = []
        retry_deferred: list[uuid.UUID] = []
        failed: list[uuid.UUID] = []
        automatically_coordinated: list[uuid.UUID] = []
        for claim in all_claims:
            try:
                run_id, _ = scheduler.create_and_link_run(
                    session, claim, now=operation_time
                )
            except AgentRunCapacityError:
                session.rollback()
                scheduler.defer_setup(
                    session, claim.occurrence_id, now=operation_time, capacity=True
                )
                session.commit()
                deferred.append(claim.occurrence_id)
                continue
            except Exception as exc:
                session.rollback()
                if scheduler.is_retryable_setup_error(exc):
                    pending = scheduler.defer_setup(
                        session,
                        claim.occurrence_id,
                        now=operation_time,
                        capacity=False,
                    )
                    session.commit()
                    (retry_deferred if pending else failed).append(claim.occurrence_id)
                else:
                    scheduler.fail_closed(
                        session,
                        claim.occurrence_id,
                        now=operation_time,
                        code="setup_failed_safe",
                    )
                    session.commit()
                    failed.append(claim.occurrence_id)
                continue
            try:
                session.commit()
                linked.append(run_id)
            except Exception:
                session.rollback()
                # A commit acknowledgement failure is never retried. A fresh
                # durable read may prove the exact link; otherwise fail closed.
                occurrence = repository.lock_occurrence(session, claim.occurrence_id)
                if (
                    occurrence is not None
                    and occurrence.agent_run_id is not None
                    and occurrence.state == "run_created"
                ):
                    linked.append(occurrence.agent_run_id)
                    session.rollback()
                else:
                    session.rollback()
                    scheduler.fail_closed(
                        session,
                        claim.occurrence_id,
                        now=operation_time,
                        code="ambiguous_commit_outcome",
                    )
                    session.commit()
                    failed.append(claim.occurrence_id)
        for claim in all_claims:
            occurrence = repository.get_automation_occurrence(
                session, claim.automation_id, claim.occurrence_id
            )
            if (
                occurrence is None
                or occurrence.agent_run_id is None
                or get_automatic_agent_definition(
                    occurrence.agent_kind, occurrence.agent_version
                )
                is None
            ):
                session.rollback()
                continue
            try:
                coordinator.coordinate_occurrence(
                    session,
                    occurrence.id,
                    resolve_planning_provider=get_planning_provider,
                    resolve_embedding_provider=get_embedding_provider,
                    provider_available=configured_embedding_provider_available,
                    resolve_daily_brief_provider=get_daily_brief_provider,
                )
                automatically_coordinated.append(occurrence.id)
            except Exception:
                session.rollback()
                # The durable Run is authoritative; the next explicit tick may
                # reconcile it, but never invokes manual recovery or replaces it.
                continue
        return scheduler.TickResult(
            materialized_ids=materialized_ids,
            claimed_ids=tuple(item.occurrence_id for item in all_claims),
            linked_run_ids=tuple(linked),
            capacity_deferred_ids=tuple(deferred),
            reclaimed_ids=tuple(item.occurrence_id for item in reclaimed),
            reconciled_ids=tuple(reconciled),
            missed_ids=missed_ids,
            retry_deferred_ids=tuple(retry_deferred),
            failed_ids=tuple(failed),
            automatically_coordinated_ids=tuple(automatically_coordinated),
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
                    "reclaimed": len(result.reclaimed_ids),
                    "reconciled": len(result.reconciled_ids),
                    "missed": len(result.missed_ids),
                    "retry_deferred": len(result.retry_deferred_ids),
                    "failed_safe": len(result.failed_ids),
                    "automatically_coordinated": len(
                        result.automatically_coordinated_ids
                    ),
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
