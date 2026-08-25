"""PostgreSQL concurrency and rollback proofs for Checkpoint 78."""

import threading
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.agent_runs import service as run_service
from app.automations import faults, scheduler
from app.db.session import get_engine
from app.main import create_app
from app.models.agent_runtime import AgentEvent, AgentRun, AgentStep, ToolInvocation
from app.models.automation import (
    Automation,
    AutomationNotification,
    AutomationOccurrence,
)
from app.repositories import automations as automation_repository
from app.schemas.agent_run import AgentRunCreate
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_scheduler_rows(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    _clean()
    yield
    _clean()


def _clean() -> None:
    with Session(get_engine()) as session:
        session.execute(delete(AutomationNotification))
        session.execute(delete(AutomationOccurrence))
        session.execute(delete(ToolInvocation))
        session.execute(delete(AgentStep))
        session.execute(delete(AgentEvent))
        session.execute(delete(AgentRun))
        session.execute(delete(Automation))
        session.commit()


def _automation(
    session: Session,
    *,
    due_at: datetime,
    lifecycle: str = "enabled",
    mode: str = "create_only",
    label: str | None = None,
) -> Automation:
    row = Automation(
        label=label or f"scheduler-{uuid.uuid4().hex}",
        automation_kind="scheduled_agent",
        agent_kind="daily_brief",
        agent_version="1",
        project_id=None,
        lifecycle=lifecycle,
        revision=1,
        execution_mode=mode,
        schedule_kind="daily",
        timezone_name="UTC",
        local_time=time(due_at.hour, due_at.minute),
        one_time_local_date=None,
        weekdays=[],
        interval_count=1,
        nonexistent_time_policy="first_valid_after_gap",
        ambiguous_time_policy="earlier_fold",
        missed_run_policy="run_once",
        retry_limit=3,
        capacity_limit=1,
        schedule_revision=0,
        next_occurrence_at=due_at,
        cancelled_at=due_at if lifecycle == "cancelled" else None,
    )
    session.add(row)
    session.flush()
    return row


def _materialized_claim(now: datetime) -> scheduler.OccurrenceClaim:
    owner = uuid.uuid4()
    with Session(get_engine()) as session:
        _automation(session, due_at=now - timedelta(minutes=1))
        scheduler.materialize_due(session, now=now)
        session.commit()
        claims = scheduler.claim_due(
            session,
            now=now,
            owner_token=owner,
            lease_duration=timedelta(seconds=60),
        )
        session.commit()
        assert len(claims) == 1
        return claims[0]


def test_materialization_filters_orders_bounds_and_advances_from_slot() -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    with Session(get_engine()) as session:
        later = _automation(session, due_at=now - timedelta(minutes=1), label="later")
        first = _automation(session, due_at=now - timedelta(minutes=2), label="first")
        _automation(session, due_at=now + timedelta(minutes=1), label="future")
        for state in ("draft", "paused", "cancelled"):
            _automation(session, due_at=now - timedelta(minutes=3), lifecycle=state)
        session.commit()
        rows = scheduler.materialize_due(session, now=now, limit=1)
        assert [row.automation_id for row in rows] == [first.id]
        session.commit()
        assert first.next_occurrence_at == now - timedelta(minutes=2) + timedelta(
            days=1
        )
        assert later.next_occurrence_at == now - timedelta(minutes=1)
        assert (
            session.scalar(select(func.count()).select_from(AutomationOccurrence)) == 1
        )


@pytest.mark.parametrize(
    "point",
    [
        faults.FaultPoint.AFTER_OCCURRENCE_INSERT,
        faults.FaultPoint.AFTER_NEXT_OCCURRENCE_ADVANCE,
    ],
)
def test_materialization_failure_rolls_back_insert_and_advance(
    point: faults.FaultPoint, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    with Session(get_engine()) as session:
        row = _automation(session, due_at=now - timedelta(minutes=1))
        original = row.next_occurrence_at
        session.commit()

        def fail(candidate: faults.FaultPoint) -> None:
            if candidate == point:
                raise faults.FaultInjectionError

        monkeypatch.setattr(faults, "fire", fail)
        with pytest.raises(faults.FaultInjectionError):
            scheduler.materialize_due(session, now=now)
        session.rollback()
        session.refresh(row)
        assert row.next_occurrence_at == original
        assert (
            session.scalar(select(func.count()).select_from(AutomationOccurrence)) == 0
        )


def test_materializer_skip_locked_and_existing_slot_uniqueness() -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    with Session(get_engine()) as setup:
        locked = _automation(setup, due_at=now - timedelta(minutes=2))
        available = _automation(setup, due_at=now - timedelta(minutes=1))
        setup.commit()
        locked_id, available_id = locked.id, available.id
    with Session(get_engine()) as blocker, Session(get_engine()) as worker:
        assert automation_repository.lock_automation(blocker, locked_id) is not None
        rows = scheduler.materialize_due(worker, now=now)
        worker.commit()
        assert [row.automation_id for row in rows] == [available_id]
        blocker.rollback()
    with Session(get_engine()) as session:
        locked_row = session.get(Automation, locked_id)
        assert locked_row is not None
        scheduler.materialize_due(session, now=now)
        session.commit()
        slot = locked_row.next_occurrence_at
        assert slot is not None
        locked_row.next_occurrence_at = now - timedelta(minutes=2)
        session.commit()
        replay = scheduler.materialize_due(session, now=now)
        session.commit()
        assert len(replay) == 1
        assert (
            session.scalar(select(func.count()).select_from(AutomationOccurrence)) == 2
        )


def test_concurrent_materializers_create_one_occurrence() -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    with Session(get_engine()) as session:
        _automation(session, due_at=now - timedelta(minutes=1))
        session.commit()
    barrier = threading.Barrier(2)

    def work() -> int:
        with Session(get_engine()) as session:
            barrier.wait(timeout=10)
            rows = scheduler.materialize_due(session, now=now)
            session.commit()
            return len(rows)

    with ThreadPoolExecutor(max_workers=2) as pool:
        counts = list(pool.map(lambda _: work(), range(2)))
    assert sorted(counts) == [0, 1]
    with Session(get_engine()) as session:
        assert (
            session.scalar(select(func.count()).select_from(AutomationOccurrence)) == 1
        )


@pytest.mark.parametrize(
    "point",
    [faults.FaultPoint.AFTER_CLAIM_STATE, faults.FaultPoint.AFTER_LEASE_GENERATION],
)
def test_claim_failure_rolls_back_state_and_lease(
    point: faults.FaultPoint, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    with Session(get_engine()) as session:
        _automation(session, due_at=now - timedelta(minutes=1))
        scheduler.materialize_due(session, now=now)
        session.commit()

        def fail(candidate: faults.FaultPoint) -> None:
            if candidate == point:
                raise faults.FaultInjectionError

        monkeypatch.setattr(faults, "fire", fail)
        with pytest.raises(faults.FaultInjectionError):
            scheduler.claim_due(
                session,
                now=now,
                owner_token=uuid.uuid4(),
                lease_duration=timedelta(seconds=60),
            )
        session.rollback()
        occurrence = session.scalar(select(AutomationOccurrence))
        assert occurrence is not None
        assert (occurrence.state, occurrence.lease_generation) == ("due", 0)
        assert occurrence.lease_owner_token is None


def test_claiming_is_bounded_deterministic_and_create_only() -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    with Session(get_engine()) as session:
        first = _automation(session, due_at=now - timedelta(minutes=2))
        _automation(session, due_at=now - timedelta(minutes=1))
        automatic = _automation(
            session,
            due_at=now - timedelta(minutes=3),
            mode="automatic_read_only",
        )
        scheduler.materialize_due(session, now=now)
        session.commit()
        claims = scheduler.claim_due(
            session,
            now=now,
            owner_token=uuid.uuid4(),
            lease_duration=timedelta(seconds=60),
            limit=1,
        )
        session.commit()
        assert len(claims) == 1
        claimed = session.get(AutomationOccurrence, claims[0].occurrence_id)
        assert claimed is not None and claimed.automation_id == first.id
        auto_occurrence = session.scalar(
            select(AutomationOccurrence).where(
                AutomationOccurrence.automation_id == automatic.id
            )
        )
        assert auto_occurrence is not None and auto_occurrence.state == "due"


def test_concurrent_claimers_claim_once() -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    with Session(get_engine()) as session:
        _automation(session, due_at=now - timedelta(minutes=1))
        scheduler.materialize_due(session, now=now)
        session.commit()
    barrier = threading.Barrier(2)

    def work() -> int:
        with Session(get_engine()) as session:
            barrier.wait(timeout=10)
            claims = scheduler.claim_due(
                session,
                now=now,
                owner_token=uuid.uuid4(),
                lease_duration=timedelta(seconds=60),
            )
            session.commit()
            return len(claims)

    with ThreadPoolExecutor(max_workers=2) as pool:
        counts = list(pool.map(lambda _: work(), range(2)))
    assert sorted(counts) == [0, 1]


def test_owner_generation_expiry_and_lifecycle_fences() -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    claim = _materialized_claim(now)
    wrong_owner = scheduler.OccurrenceClaim(
        claim.occurrence_id, claim.automation_id, uuid.uuid4(), claim.lease_generation
    )
    wrong_generation = scheduler.OccurrenceClaim(
        claim.occurrence_id,
        claim.automation_id,
        claim.owner_token,
        claim.lease_generation + 1,
    )
    for invalid, instant in (
        (wrong_owner, now),
        (wrong_generation, now),
        (claim, now + timedelta(seconds=60)),
    ):
        with Session(get_engine()) as session:
            with pytest.raises(scheduler.ClaimFenceError):
                scheduler.renew_claim(
                    session,
                    invalid,
                    now=instant,
                    lease_duration=timedelta(seconds=60),
                )
            session.rollback()
    with Session(get_engine()) as session:
        with pytest.raises(scheduler.ClaimFenceError):
            scheduler.create_and_link_run(session, wrong_owner, now=now)
        session.rollback()
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 0


@pytest.mark.parametrize("mutation", ["pause", "cancel", "edit"])
def test_lifecycle_and_edit_race_before_run_link(mutation: str) -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    claim = _materialized_claim(now)
    with Session(get_engine()) as session:
        automation = session.get(Automation, claim.automation_id)
        assert automation is not None
        if mutation == "pause":
            automation.lifecycle = "paused"
            automation.revision += 1
        elif mutation == "cancel":
            automation.lifecycle = "cancelled"
            automation.cancelled_at = now
            automation.next_occurrence_at = None
            automation.revision += 1
        else:
            automation.label = "edited after claim"
            automation.revision += 1
        session.commit()
        with pytest.raises(scheduler.ClaimFenceError):
            scheduler.create_and_link_run(session, claim, now=now)
        session.rollback()
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 0


@pytest.mark.parametrize(
    "point",
    [faults.FaultPoint.AFTER_RUN_CREATION, faults.FaultPoint.AFTER_RUN_LINK],
)
def test_run_link_failure_rolls_back_run_and_link(
    point: faults.FaultPoint, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    claim = _materialized_claim(now)

    def fail(candidate: faults.FaultPoint) -> None:
        if candidate == point:
            raise faults.FaultInjectionError

    monkeypatch.setattr(faults, "fire", fail)
    with Session(get_engine()) as session:
        with pytest.raises(faults.FaultInjectionError):
            scheduler.create_and_link_run(session, claim, now=now)
        session.rollback()
        occurrence = session.get(AutomationOccurrence, claim.occurrence_id)
        assert occurrence is not None
        assert occurrence.state == "claimed" and occurrence.agent_run_id is None
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 0


def test_concurrent_link_and_replay_resolve_one_inert_run() -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    claim = _materialized_claim(now)
    barrier = threading.Barrier(2)

    def work() -> tuple[uuid.UUID, bool]:
        with Session(get_engine()) as session:
            barrier.wait(timeout=10)
            result = scheduler.create_and_link_run(session, claim, now=now)
            session.commit()
            return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: work(), range(2)))
    assert results[0][0] == results[1][0]
    assert sorted(created for _, created in results) == [False, True]
    with Session(get_engine()) as session:
        occurrence = session.get(AutomationOccurrence, claim.occurrence_id)
        assert occurrence is not None and occurrence.state == "run_created"
        run = session.get(AgentRun, occurrence.agent_run_id)
        assert run is not None and run.state == "created"
        assert run.agent_kind == "daily_brief"
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 1
        assert session.scalar(select(func.count()).select_from(AgentStep)) == 0
        assert session.scalar(select(func.count()).select_from(ToolInvocation)) == 0


def test_capacity_rejection_preserves_durable_claim() -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    claim = _materialized_claim(now)
    with Session(get_engine()) as session:
        for index in range(run_service.MAX_ACTIVE_RUNS):
            request = AgentRunCreate(
                project_id=None,
                agent_kind="research-agent",
                agent_version="1",
                goal_summary=f"capacity {index}",
            )
            key = f"capacity-{index}"
            run_service.create_run(
                session,
                request,
                idempotency_key_hash=run_service.hash_idempotency_key(key),
                fingerprint=run_service.normalized_request_fingerprint(request),
                now=now,
            )
        session.commit()
        with pytest.raises(run_service.AgentRunCapacityError):
            scheduler.create_and_link_run(session, claim, now=now)
        session.rollback()
        occurrence = session.get(AutomationOccurrence, claim.occurrence_id)
        assert occurrence is not None
        assert occurrence.state == "claimed" and occurrence.agent_run_id is None
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 32


def test_app_creation_has_no_scheduler_side_effect() -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    with Session(get_engine()) as session:
        _automation(session, due_at=now - timedelta(minutes=1))
        session.commit()
    create_app()
    with Session(get_engine()) as session:
        assert (
            session.scalar(select(func.count()).select_from(AutomationOccurrence)) == 0
        )
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 0


def test_expired_claim_reclaims_and_fences_old_generation() -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    old = _materialized_claim(now)
    new_owner = uuid.uuid4()
    with Session(get_engine()) as session:
        assert (
            scheduler.reclaim_expired(
                session,
                now=now + timedelta(seconds=59),
                owner_token=new_owner,
                lease_duration=timedelta(seconds=60),
            )
            == []
        )
        session.commit()
        reclaimed = scheduler.reclaim_expired(
            session,
            now=now + timedelta(seconds=60),
            owner_token=new_owner,
            lease_duration=timedelta(seconds=60),
        )
        session.commit()
        assert len(reclaimed) == 1
        assert reclaimed[0].lease_generation == old.lease_generation + 1
        with pytest.raises(scheduler.ClaimFenceError):
            scheduler.create_and_link_run(session, old, now=now + timedelta(seconds=60))
        session.rollback()


@pytest.mark.parametrize(
    "policy,expected_state", [("skip", "missed"), ("run_once", "due")]
)
def test_missed_policy_materializes_only_latest_slot(
    policy: str, expected_state: str
) -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    with Session(get_engine()) as session:
        automation = _automation(session, due_at=now - timedelta(days=30))
        automation.missed_run_policy = policy
        session.commit()
        rows = scheduler.materialize_due(session, now=now)
        session.commit()
        assert len(rows) == 1
        assert rows[0].state == expected_state
        assert rows[0].scheduled_at == now
        assert automation.next_occurrence_at == now + timedelta(days=1)
        assert (
            session.scalar(select(func.count()).select_from(AutomationOccurrence)) == 1
        )
        if policy == "skip":
            assert rows[0].safe_disposition_code == "missed_lookback_bounded"


def test_repeated_restart_reconciles_exact_link_without_replacement() -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    claim = _materialized_claim(now)
    with Session(get_engine()) as session:
        run_id, created = scheduler.create_and_link_run(session, claim, now=now)
        session.commit()
        assert created
        for _ in range(2):
            assert scheduler.reconcile_linked(session, now=now) == [claim.occurrence_id]
            session.commit()
        occurrence = session.get(AutomationOccurrence, claim.occurrence_id)
        assert occurrence is not None and occurrence.agent_run_id == run_id
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 1


def test_linked_terminal_run_reconciliation_is_idempotent() -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    claim = _materialized_claim(now)
    with Session(get_engine()) as session:
        run_id, _ = scheduler.create_and_link_run(session, claim, now=now)
        session.commit()
        run = session.get(AgentRun, run_id)
        assert run is not None
        run.state = "cancelled"
        run.started_at = run.created_at
        run.finished_at = run.created_at
        session.commit()
        assert scheduler.reconcile_linked(session, now=now) == [claim.occurrence_id]
        session.commit()
        occurrence = session.get(AutomationOccurrence, claim.occurrence_id)
        assert occurrence is not None and occurrence.state == "failed"
        assert scheduler.reconcile_linked(session, now=now) == []
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 1


def test_retry_budget_timing_and_capacity_deferral() -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    claim = _materialized_claim(now)
    with Session(get_engine()) as session:
        assert scheduler.defer_setup(
            session, claim.occurrence_id, now=now, capacity=True
        )
        session.commit()
        occurrence = session.get(AutomationOccurrence, claim.occurrence_id)
        assert occurrence is not None
        assert occurrence.attempt_count == 0 and occurrence.state == "due"
        assert occurrence.retry_not_before == now + scheduler.retry_delay(
            occurrence.id, 1
        )
        claims = scheduler.claim_due(
            session,
            now=now,
            owner_token=uuid.uuid4(),
            lease_duration=timedelta(seconds=60),
        )
        assert claims == []
        session.rollback()


def test_retry_exhaustion_is_terminal_and_operator_visible() -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    claim = _materialized_claim(now)
    with Session(get_engine()) as session:
        occurrence = session.get(AutomationOccurrence, claim.occurrence_id)
        assert occurrence is not None
        occurrence.attempt_count = 2
        session.commit()
        assert not scheduler.defer_setup(
            session, claim.occurrence_id, now=now, capacity=False
        )
        session.commit()
        assert occurrence.state == "failed"
        assert occurrence.safe_error_code == "setup_retry_exhausted"
        assert (
            session.scalar(select(func.count()).select_from(AutomationNotification))
            == 1
        )


def test_concurrent_recovery_workers_reclaim_once() -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    _materialized_claim(now)
    barrier = threading.Barrier(2)

    def work() -> int:
        with Session(get_engine()) as session:
            barrier.wait(timeout=10)
            rows = scheduler.reclaim_expired(
                session,
                now=now + timedelta(seconds=60),
                owner_token=uuid.uuid4(),
                lease_duration=timedelta(seconds=60),
            )
            session.commit()
            return len(rows)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: work(), range(2))) == [0, 1]


def test_backward_clock_does_not_reopen_terminal_slot() -> None:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    with Session(get_engine()) as session:
        automation = _automation(session, due_at=now - timedelta(days=2))
        automation.missed_run_policy = "skip"
        session.commit()
        rows = scheduler.materialize_due(session, now=now)
        session.commit()
        assert len(rows) == 1 and rows[0].state == "missed"
        assert scheduler.materialize_due(session, now=now - timedelta(days=1)) == []
        assert (
            session.scalar(select(func.count()).select_from(AutomationOccurrence)) == 1
        )


def test_retry_classifier_is_closed() -> None:
    transient = OperationalError("statement", {}, ConnectionError("offline"))
    assert scheduler.is_retryable_setup_error(transient)
    assert not scheduler.is_retryable_setup_error(scheduler.SchedulerValidationError())
    assert not scheduler.is_retryable_setup_error(IntegrityError("statement", {}, None))
