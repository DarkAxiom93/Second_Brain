"""Checkpoint 94 connector-owned scheduling and fencing proofs."""

import uuid
from collections.abc import Generator
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.connectors import scheduler
from app.db.session import get_engine
from app.main import create_app
from app.models.agent_runtime import AgentRun
from app.models.connector import ConnectorAccount, ConnectorSyncRun
from app.models.connector_schedule import (
    ConnectorRefreshNotification,
    ConnectorRefreshOccurrence,
    ConnectorRefreshSchedule,
)
from app.models.external_item_import import ExternalItemImport
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        for model in (
            ConnectorRefreshNotification,
            ConnectorRefreshOccurrence,
            ConnectorRefreshSchedule,
            ConnectorSyncRun,
            ConnectorAccount,
        ):
            session.execute(delete(model))
        session.commit()
    yield
    with Session(get_engine()) as session:
        for model in (
            ConnectorRefreshNotification,
            ConnectorRefreshOccurrence,
            ConnectorRefreshSchedule,
            ConnectorSyncRun,
            ConnectorAccount,
        ):
            session.execute(delete(model))
        session.commit()


def _account(client: TestClient) -> dict[str, object]:
    created = client.post(
        "/connector-accounts",
        json={
            "external_account_identity": "operator-account",
            "credential_reference": "sbcred:v1:12345678-1234-4123-8123-123456789abc",
            "scope": {"kind": "unassigned", "project_id": None},
            "repositories": ["owner/repository"],
        },
    ).json()
    return client.post(
        f"/connector-accounts/{created['id']}/re-enable", json={"expected_revision": 0}
    ).json()


def _schedule(client: TestClient, account_id: str) -> dict[str, object]:
    response = client.post(
        f"/connector-accounts/{account_id}/refresh-schedule",
        json={
            "schedule": {
                "kind": "daily",
                "timezone_name": "UTC",
                "local_time": "08:00:00",
            },
            "missed_run_policy": "run_once",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_default_draft_lifecycle_cas_and_one_per_account() -> None:
    client = TestClient(create_app())
    account = _account(client)
    row = _schedule(client, str(account["id"]))
    assert row["lifecycle"] == "draft" and row["next_occurrence_at"] is None
    assert (
        client.post(
            f"/connector-accounts/{account['id']}/refresh-schedule",
            json={
                "schedule": {
                    "kind": "daily",
                    "timezone_name": "UTC",
                    "local_time": "09:00:00",
                }
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/connector-refresh-schedules/{row['id']}/enable",
            json={"expected_revision": 9},
        ).status_code
        == 409
    )
    enabled = client.post(
        f"/connector-refresh-schedules/{row['id']}/enable",
        json={"expected_revision": 0},
    ).json()
    paused = client.post(
        f"/connector-refresh-schedules/{row['id']}/pause", json={"expected_revision": 1}
    ).json()
    resumed = client.post(
        f"/connector-refresh-schedules/{row['id']}/resume",
        json={"expected_revision": 2},
    ).json()
    cancelled = client.post(
        f"/connector-refresh-schedules/{row['id']}/cancel",
        json={"expected_revision": 3},
    ).json()
    assert [
        enabled["lifecycle"],
        paused["lifecycle"],
        resumed["lifecycle"],
        cancelled["lifecycle"],
    ] == ["enabled", "paused", "enabled", "cancelled"]
    assert (
        client.post(
            f"/connector-refresh-schedules/{row['id']}/resume",
            json={"expected_revision": 4},
        ).status_code
        == 409
    )


def test_materialize_claim_link_is_deterministic_and_never_agent_or_import() -> None:
    client = TestClient(create_app())
    account = _account(client)
    row = _schedule(client, str(account["id"]))
    enabled = client.post(
        f"/connector-refresh-schedules/{row['id']}/enable",
        json={"expected_revision": 0},
    ).json()
    now = datetime.fromisoformat(
        str(enabled["next_occurrence_at"]).replace("Z", "+00:00")
    )
    with Session(get_engine()) as session:
        before_agents = session.scalar(select(func.count()).select_from(AgentRun))
        before_imports = session.scalar(
            select(func.count()).select_from(ExternalItemImport)
        )
        first = scheduler.materialize_due(session, now=now)
        session.commit()
        assert len(first) == 1
        assert scheduler.materialize_due(session, now=now) == []
        claims = scheduler.claim_due(
            session,
            now=now,
            owner_token=uuid.uuid4(),
            lease_duration=timedelta(seconds=60),
        )
        session.commit()
        assert len(claims) == 1
        run = scheduler.create_and_link_sync(session, claims[0])
        session.commit()
        assert (
            run.trigger_kind == "scheduled"
            and run.trigger_identity.startswith("connector_schedule_")
            and len(run.trigger_identity) == 83
        )
        occurrence = session.get(ConnectorRefreshOccurrence, claims[0].occurrence_id)
        assert occurrence is not None and occurrence.connector_sync_run_id == run.id
        assert (
            session.scalar(select(func.count()).select_from(AgentRun)) == before_agents
        )
        assert (
            session.scalar(select(func.count()).select_from(ExternalItemImport))
            == before_imports
        )


def test_expired_lease_reclaims_once_and_stale_owner_is_fenced() -> None:
    client = TestClient(create_app())
    account = _account(client)
    row = _schedule(client, str(account["id"]))
    enabled = client.post(
        f"/connector-refresh-schedules/{row['id']}/enable",
        json={"expected_revision": 0},
    ).json()
    now = datetime.fromisoformat(
        str(enabled["next_occurrence_at"]).replace("Z", "+00:00")
    )
    with Session(get_engine()) as session:
        scheduler.materialize_due(session, now=now)
        session.commit()
        old = scheduler.claim_due(
            session,
            now=now,
            owner_token=uuid.uuid4(),
            lease_duration=timedelta(seconds=10),
        )[0]
        session.commit()
        new = scheduler.reclaim_expired(
            session,
            now=now + timedelta(seconds=10),
            owner_token=uuid.uuid4(),
            lease_duration=timedelta(seconds=10),
        )
        session.commit()
        assert len(new) == 1 and new[0].lease_generation == old.lease_generation + 1
        with pytest.raises(ValueError, match="stale"):
            scheduler.create_and_link_sync(session, old)
