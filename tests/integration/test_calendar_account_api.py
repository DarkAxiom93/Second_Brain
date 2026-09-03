"""Checkpoint 101 Calendar metadata lifecycle acceptance."""

import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.calendar.dependencies import (
    calendar_credential_dependency,
    calendar_transport_factory_dependency,
)
from app.calendar.google import CalendarPage, FakeCalendarTransport
from app.credentials import CredentialReference
from app.db.session import get_engine
from app.google_oauth.service import RevocationResult
from app.main import create_app
from app.models.calendar import (
    CalendarAccountRevision,
    CalendarEventRevision,
    CalendarIdentity,
    CalendarSyncRun,
)
from app.models.project import Project
from tests.integration.conftest import verify_connected_test_database

REFERENCE = "sbcred:v1:12345678-1234-4123-8123-123456789abc"
FINGERPRINT = "a" * 64


class FakeBoundary:
    def __init__(self) -> None:
        self.available = True
        self.fingerprint = FINGERPRINT
        self.revocation = RevocationResult(True, True)
        self.revoked: list[str] = []

    def status(self, reference: CredentialReference) -> dict[str, object]:
        if not self.available:
            from app.credentials import CredentialStoreMissingError

            raise CredentialStoreMissingError
        return {
            "status": "authorized",
            "credential_reference": str(reference),
            "account_fingerprint": self.fingerprint,
            "generation": 1,
        }

    def revoke(self, reference: CredentialReference) -> RevocationResult:
        self.revoked.append(str(reference))
        return self.revocation

    def refresh(self, reference: CredentialReference) -> str:
        return "obviously-fake-access-token"


@pytest.fixture(autouse=True)
def clean_calendar(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)

    def clean() -> None:
        with Session(get_engine()) as session:
            session.execute(delete(CalendarEventRevision))
            session.execute(delete(CalendarSyncRun))
            session.execute(delete(CalendarIdentity))
            session.execute(delete(CalendarAccountRevision))
            session.commit()

    clean()
    yield
    clean()


@pytest.fixture
def client() -> tuple[TestClient, FakeBoundary, FastAPI]:
    boundary = FakeBoundary()
    app = create_app()
    app.dependency_overrides[calendar_credential_dependency] = lambda: boundary
    return TestClient(app), boundary, app


def payload(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "credential_reference": REFERENCE,
        "account_fingerprint": FINGERPRINT,
        "scope": {"kind": "unassigned", "project_id": None},
        "calendar_ids": ["primary", "opaque/calendar?value=#fragment"],
    }
    value.update(changes)
    return value


def test_create_list_read_safe_projection_and_hostile_ids(
    client: tuple[TestClient, FakeBoundary, FastAPI],
) -> None:
    http, _, _ = client
    response = http.post("/calendar-accounts", json=payload())
    assert response.status_code == 201
    account = response.json()
    assert account["lifecycle"] == "enabled"
    assert account["credential_status"] == "valid"
    assert account["scope"] == {"kind": "unassigned", "project_id": None}
    assert account["calendar_ids"] == ["opaque/calendar?value=#fragment", "primary"]
    forbidden = {
        "credential_reference",
        "refresh_token",
        "access_token",
        "sub",
        "email",
        "profile",
        "configuration_state",
    }
    assert forbidden.isdisjoint(account)
    assert "sbcred:" not in response.text
    assert http.get(f"/calendar-accounts/{account['id']}").json() == account
    assert http.get("/calendar-accounts").json() == [account]


def test_manual_full_refresh_persists_minimized_pages_and_safe_history(
    client: tuple[TestClient, FakeBoundary, FastAPI],
) -> None:
    http, _, app = client
    created = http.post(
        "/calendar-accounts", json=payload(calendar_ids=["z-calendar", "a-calendar"])
    ).json()
    event = {
        "id": "event-1",
        "status": "confirmed",
        "eventType": "default",
        "summary": "Planning",
        "visibility": "default",
        "etag": '"one"',
        "updated": "2026-09-03T10:00:00Z",
        "start": {"dateTime": "2026-09-04T10:00:00+03:00"},
        "end": {"dateTime": "2026-09-04T11:00:00+03:00"},
    }
    transport = FakeCalendarTransport(
        [CalendarPage([event], None), CalendarPage([], None)]
    )
    app.dependency_overrides[calendar_transport_factory_dependency] = lambda: (
        lambda: transport
    )
    response = http.post(
        f"/calendar-accounts/{created['id']}/refresh",
        json={"expected_revision": 1},
    )
    assert response.status_code == 200, response.text
    assert [call.calendar_id for call in transport.calls] == [
        "a-calendar",
        "z-calendar",
    ]
    assert [run["status"] for run in response.json()] == ["succeeded", "succeeded"]
    assert sum(run["items_written"] for run in response.json()) == 1
    history = http.get(f"/calendar-accounts/{created['id']}/sync-runs").json()
    assert len(history) == 2
    with Session(get_engine()) as session:
        stored = session.scalars(select(CalendarEventRevision)).all()
        assert len(stored) == 1
        assert stored[0].title == "Planning"
        assert stored[0].state == "current"


def test_exact_project_and_unassigned_are_distinct(
    client: tuple[TestClient, FakeBoundary, FastAPI],
) -> None:
    http, _, _ = client
    with Session(get_engine()) as session:
        project = Project(name="calendar-" + uuid.uuid4().hex)
        session.add(project)
        session.commit()
        project_id = str(project.id)
    assigned = http.post(
        "/calendar-accounts",
        json=payload(
            scope={"kind": "project", "project_id": project_id},
            calendar_ids=["assigned"],
        ),
    )
    assert assigned.status_code == 201
    assert assigned.json()["scope"] == {"kind": "project", "project_id": project_id}
    for scope in (
        {"kind": "project", "project_id": None},
        {"kind": "unassigned", "project_id": project_id},
        {"kind": "project", "project_id": str(uuid.uuid4())},
    ):
        assert http.post(
            "/calendar-accounts", json=payload(scope=scope, calendar_ids=[str(scope)])
        ).status_code in {404, 422}


@pytest.mark.parametrize(
    "ids",
    [
        [],
        [str(x) for x in range(11)],
        ["duplicate", "duplicate"],
        [" padded"],
        [""],
        ["x" * 1025],
    ],
)
def test_allowlist_bounds_and_exact_validation(
    client: tuple[TestClient, FakeBoundary, FastAPI], ids: list[str]
) -> None:
    assert (
        client[0].post("/calendar-accounts", json=payload(calendar_ids=ids)).status_code
        == 422
    )


def test_fingerprint_missing_credential_and_cross_account_calendar_protection(
    client: tuple[TestClient, FakeBoundary, FastAPI],
) -> None:
    http, boundary, _ = client
    boundary.fingerprint = "b" * 64
    assert http.post("/calendar-accounts", json=payload()).status_code == 409
    boundary.available = False
    assert http.post("/calendar-accounts", json=payload()).status_code == 409
    boundary.available = True
    boundary.fingerprint = FINGERPRINT
    assert (
        http.post(
            "/calendar-accounts", json=payload(calendar_ids=["owned"])
        ).status_code
        == 201
    )
    assert (
        http.post(
            "/calendar-accounts", json=payload(calendar_ids=["owned"])
        ).status_code
        == 422
    )
    boundary.fingerprint = "b" * 64
    assert (
        http.post(
            "/calendar-accounts",
            json=payload(account_fingerprint="b" * 64, calendar_ids=["owned"]),
        ).status_code
        == 422
    )


def test_disable_edit_reenable_revision_cas_and_history(
    client: tuple[TestClient, FakeBoundary, FastAPI],
) -> None:
    http, boundary, _ = client
    created = http.post("/calendar-accounts", json=payload()).json()
    account_id = created["id"]
    disabled = http.post(
        f"/calendar-accounts/{account_id}/disable", json={"expected_revision": 1}
    ).json()
    assert disabled["configuration_revision"] == 2
    stale = http.patch(
        f"/calendar-accounts/{account_id}",
        json={
            "expected_revision": 1,
            "scope": {"kind": "unassigned", "project_id": None},
            "calendar_ids": ["changed"],
        },
    )
    assert stale.status_code == 409
    updated = http.patch(
        f"/calendar-accounts/{account_id}",
        json={
            "expected_revision": 2,
            "scope": {"kind": "unassigned", "project_id": None},
            "calendar_ids": ["changed"],
        },
    ).json()
    assert updated["configuration_revision"] == 3
    boundary.available = False
    assert (
        http.post(
            f"/calendar-accounts/{account_id}/re-enable", json={"expected_revision": 3}
        ).status_code
        == 409
    )
    boundary.available = True
    enabled = http.post(
        f"/calendar-accounts/{account_id}/re-enable", json={"expected_revision": 3}
    ).json()
    assert (enabled["lifecycle"], enabled["configuration_revision"]) == ("enabled", 4)
    with Session(get_engine()) as session:
        rows = list(
            session.scalars(
                select(CalendarAccountRevision)
                .where(
                    CalendarAccountRevision.configuration_id == uuid.UUID(account_id)
                )
                .order_by(CalendarAccountRevision.configuration_revision)
            )
        )
        assert [
            (x.configuration_revision, x.lifecycle, x.project_id) for x in rows
        ] == [
            (1, "enabled", None),
            (2, "disabled", None),
            (3, "disabled", None),
            (4, "enabled", None),
        ]


def test_concurrent_stale_disable_has_one_winner(
    client: tuple[TestClient, FakeBoundary, FastAPI],
) -> None:
    created = client[0].post("/calendar-accounts", json=payload()).json()

    def disable() -> int:
        return (
            TestClient(client[2])
            .post(
                f"/calendar-accounts/{created['id']}/disable",
                json={"expected_revision": 1},
            )
            .status_code
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: disable(), range(2))) == [200, 409]


def test_revoke_projects_success_and_partial_outcome_preserving_history(
    client: tuple[TestClient, FakeBoundary, FastAPI],
) -> None:
    http, boundary, _ = client
    created = http.post("/calendar-accounts", json=payload()).json()
    boundary.revocation = RevocationResult(False, True)
    result = http.post(
        f"/calendar-accounts/{created['id']}/revoke", json={"expected_revision": 1}
    )
    assert result.status_code == 200
    body = result.json()
    assert (
        body["account"]["lifecycle"],
        body["account"]["credential_status"],
        body["provider_revoked"],
        body["local_deleted"],
    ) == ("revoked", "revoked", False, True)
    assert boundary.revoked == [REFERENCE]
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count(CalendarAccountRevision.id))) == 2
        assert session.scalar(select(func.count(CalendarIdentity.id))) == 4


def test_zero_calendar_data_or_protected_domain_calls(
    client: tuple[TestClient, FakeBoundary, FastAPI], monkeypatch: pytest.MonkeyPatch
) -> None:
    import socket

    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("no provider data request")
        ),
    )
    tables = (
        "calendar_sync_runs",
        "calendar_event_revisions",
        "memories",
        "agent_runs",
        "automations",
    )
    with Session(get_engine()) as session:
        before = {
            name: session.execute(text(f"SELECT count(*) FROM {name}")).scalar_one()
            for name in tables
        }
    assert client[0].post("/calendar-accounts", json=payload()).status_code == 201
    with Session(get_engine()) as session:
        after = {
            name: session.execute(text(f"SELECT count(*) FROM {name}")).scalar_one()
            for name in tables
        }
    assert before == after
