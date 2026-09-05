"""Checkpoint 107 joined Local V1.5 Calendar acceptance."""

import json
import urllib.parse
import uuid
import zipfile
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.orm import Session

from app.calendar.dependencies import (
    calendar_credential_dependency,
    calendar_transport_factory_dependency,
)
from app.calendar.google import (
    CalendarPage,
    FakeCalendarTransport,
)
from app.credentials import CredentialReference
from app.credentials.fake import FakeCredentialStore
from app.db.session import get_engine
from app.google_oauth.contract import SCOPES, TokenResponse
from app.google_oauth.identity import account_fingerprint
from app.google_oauth.service import GoogleOAuthService
from app.main import create_app
from app.models import AgentRun, Automation, Memory, MemoryProposal, Project, Source
from app.models.calendar import (
    CalendarAccountRevision,
    CalendarEventObservation,
    CalendarEventRevision,
    CalendarIdentity,
    CalendarSyncRun,
)
from app.project_export.models import CURRENT_DATABASE_REVISION
from app.project_export.service import export_project
from tests.integration.conftest import verify_connected_test_database

CLIENT_ID = "cp107-fake-client.apps.googleusercontent.com"
REFERENCE = CredentialReference("sbcred:v1:10700000-0000-4000-8000-000000000107")
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWK = json.loads(RSAAlgorithm.to_jwk(PRIVATE_KEY.public_key())) | {
    "kid": "cp107-fake-key",
    "alg": "RS256",
    "use": "sig",
}
SUBJECT = "cp107-approved-synthetic-subject"
EXCLUDED_CANARY = "cp107-excluded-private-provider-content"
HOSTILE = "<script>alert(107)</script> [link](javascript:alert(1)) \u202e"
CONTROL_CANARY = "cp107-control-\u0007-canary"


class _Callback:
    redirect_uri = "http://127.0.0.1:43107/oauth/google/callback"

    def __init__(self) -> None:
        self.state = ""

    def wait(self) -> object:
        return type("Result", (), {"code": "cp107-code", "state": self.state})()

    def close(self) -> None:
        return None


class _Provider:
    def __init__(self) -> None:
        self.nonce = ""

    def exchange_code(self, **kwargs: str) -> TokenResponse:
        assert kwargs["code"] == "cp107-code"
        now = datetime.now(UTC)
        token = jwt.encode(
            {
                "iss": "https://accounts.google.com",
                "aud": CLIENT_ID,
                "exp": now + timedelta(minutes=5),
                "iat": now,
                "nonce": self.nonce,
                "sub": SUBJECT,
                "email": EXCLUDED_CANARY,
            },
            PRIVATE_KEY,
            algorithm="RS256",
            headers={"kid": "cp107-fake-key"},
        )
        return TokenResponse(
            "cp107-fake-access",
            3600,
            " ".join(reversed(SCOPES)),
            token,
            "cp107-refresh",
        )

    def refresh(self, **kwargs: str) -> TokenResponse:
        assert kwargs["refresh_token"] == "cp107-refresh"
        return TokenResponse("cp107-fake-access", 3600, " ".join(SCOPES), None, None)

    def revoke(self, **kwargs: str) -> None:
        assert kwargs["token"] == "cp107-refresh"

    def jwks(self) -> dict[str, object]:
        return {"keys": [JWK]}


def _authorized_boundary() -> tuple[GoogleOAuthService, FakeCredentialStore]:
    store = FakeCredentialStore(reference_factory=lambda: REFERENCE)
    provider = _Provider()
    callback = _Callback()

    def browser(url: str) -> bool:
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        assert set(query["scope"][0].split()) == set(SCOPES)
        assert "email" not in query["scope"] and "profile" not in query["scope"]
        callback.state = query["state"][0]
        provider.nonce = query["nonce"][0]
        return True

    service = GoogleOAuthService(
        client_id=CLIENT_ID,
        store=store,
        provider=provider,
        callback_factory=lambda: callback,  # type: ignore[arg-type]
        browser_open=browser,
    )
    authorized = service.authorize()
    assert authorized.credential_reference == REFERENCE
    assert authorized.account_fingerprint == account_fingerprint(SUBJECT)
    assert EXCLUDED_CANARY.encode() not in store.read(REFERENCE)
    return service, store


@pytest.fixture(autouse=True)
def clean_acceptance_rows(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)

    def clean() -> None:
        with Session(get_engine()) as session:
            for model in (
                CalendarEventObservation,
                CalendarEventRevision,
                CalendarSyncRun,
                CalendarIdentity,
                CalendarAccountRevision,
            ):
                session.execute(delete(model))
            session.execute(delete(Project).where(Project.name.like("cp107-%")))
            session.commit()

    clean()
    yield
    clean()


def _event(event_id: str, **changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": event_id,
        "status": "confirmed",
        "eventType": "default",
        "summary": f"CP107 {event_id}",
        "visibility": "default",
        "etag": f'"{event_id}-one"',
        "updated": "2026-09-05T08:00:00Z",
        "start": {
            "dateTime": "2026-09-06T10:00:00+03:00",
            "timeZone": "Asia/Jerusalem",
        },
        "end": {"dateTime": "2026-09-06T11:00:00+03:00", "timeZone": "Asia/Jerusalem"},
    }
    value.update(changes)
    return value


def _events(
    *, changed: bool = False, omit_recurring: bool = False
) -> list[dict[str, object]]:
    ordinary = _event(
        "ordinary",
        summary="CP107 changed" if changed else HOSTILE,
        etag='"ordinary-two"' if changed else '"ordinary-one"',
        updated="2026-09-05T09:00:00Z" if changed else "2026-09-05T08:00:00Z",
    )
    values = [ordinary]
    if not omit_recurring:
        values.append(
            _event(
                "recurring-exception",
                recurringEventId="series-107",
                originalStartTime={"dateTime": "2026-09-07T10:00:00+03:00"},
                start={
                    "dateTime": "2026-09-07T12:00:00+03:00",
                    "timeZone": "Asia/Jerusalem",
                },
                end={
                    "dateTime": "2026-09-07T13:00:00+03:00",
                    "timeZone": "Asia/Jerusalem",
                },
            )
        )
    values.extend(
        [
            _event("private", summary=EXCLUDED_CANARY, visibility="private"),
            _event("special", eventType="focusTime", summary=EXCLUDED_CANARY),
            _event(
                "all-day",
                start={"date": "2026-09-08"},
                end={"date": "2026-09-09"},
            ),
        ]
    )
    return values


def _client(
    pages: list[list[dict[str, object]] | Exception],
) -> tuple[TestClient, GoogleOAuthService, list[FakeCalendarTransport]]:
    boundary, _ = _authorized_boundary()
    app = create_app()
    app.dependency_overrides[calendar_credential_dependency] = lambda: boundary
    transports: list[FakeCalendarTransport] = []

    def factory() -> FakeCalendarTransport:
        page = pages.pop(0)
        response = page if isinstance(page, Exception) else CalendarPage(page, None)
        transport = FakeCalendarTransport([response])
        transports.append(transport)
        return transport

    app.dependency_overrides[calendar_transport_factory_dependency] = lambda: factory
    return TestClient(app), boundary, transports


def _create_account(client: TestClient, project_id: str | None) -> dict[str, object]:
    scope = (
        {"kind": "unassigned", "project_id": None}
        if project_id is None
        else {"kind": "project", "project_id": project_id}
    )
    response = client.post(
        "/calendar-accounts",
        json={
            "credential_reference": str(REFERENCE),
            "account_fingerprint": account_fingerprint(SUBJECT),
            "scope": scope,
            "calendar_ids": ["cp107-approved-calendar"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_joined_project_authorize_refresh_browse_reconcile_revoke_and_privacy(
    tmp_path: Path,
) -> None:
    client, _, transports = _client(
        [_events(), _events(), _events(changed=True, omit_recurring=True), _events()]
    )
    project_a = client.post(
        "/projects", json={"name": f"cp107-a-{uuid.uuid4().hex}"}
    ).json()
    project_b = client.post(
        "/projects", json={"name": f"cp107-b-{uuid.uuid4().hex}"}
    ).json()
    with Session(get_engine()) as session:
        protected_before = {
            model.__tablename__: session.scalar(select(func.count(model.id)))
            for model in (Memory, MemoryProposal, AgentRun, Automation, Source)
        }
    account = _create_account(client, project_a["id"])

    states = ("current", "current", "stale", "current")
    for expected_recurring_state in states:
        refreshed = client.post(
            f"/calendar-accounts/{account['id']}/refresh",
            json={"expected_revision": 1},
        )
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()[0]["status"] == "succeeded"
        before_browse_calls = sum(len(transport.calls) for transport in transports)
        listed = client.get("/calendar-events", params={"scope": project_a["id"]})
        assert listed.status_code == 200
        items = listed.json()["items"]
        recurring = next(
            item for item in items if item["title"] == "CP107 recurring-exception"
        )
        assert recurring["effective_state"] == expected_recurring_state
        assert (
            client.get(
                f"/calendar-events/{recurring['id']}",
                params={"scope": project_a["id"]},
            ).json()
            == recurring
        )
        assert (
            sum(len(transport.calls) for transport in transports) == before_browse_calls
        )

    current = client.get("/calendar-events", params={"scope": project_a["id"]}).json()[
        "items"
    ]
    assert {item["title"] for item in current} >= {
        HOSTILE,
        "Busy",
        "Focus time",
    }
    assert (
        client.get("/calendar-events", params={"scope": project_b["id"]}).json()[
            "items"
        ]
        == []
    )
    assert (
        client.get("/calendar-events", params={"scope": "unassigned"}).json()["items"]
        == []
    )
    event_id = current[0]["id"]
    assert (
        client.get(
            f"/calendar-events/{event_id}", params={"scope": project_b["id"]}
        ).status_code
        == 404
    )
    assert client.get(
        "/calendar-events", params={"scope": project_b["id"], "cursor": "forged"}
    ).status_code in {404, 422}

    public_text = json.dumps(current)
    assert EXCLUDED_CANARY not in public_text
    assert not {
        "description",
        "location",
        "attendees",
        "organizer",
        "conferenceData",
        "attachments",
        "reminders",
        "extendedProperties",
        "provider_url",
        "htmlLink",
    } & set().union(*(set(item) for item in current))
    assert all("href" not in item and "url" not in item for item in current)

    with Session(get_engine()) as session:
        revisions = list(session.scalars(select(CalendarEventRevision)))
        observations = list(session.scalars(select(CalendarEventObservation)))
        runs = list(
            session.scalars(
                select(CalendarSyncRun).order_by(CalendarSyncRun.created_at)
            )
        )
        assert len(revisions) == 6
        assert sorted(
            revision.application_revision
            for revision in revisions
            if revision.provider_event_id == "ordinary"
        ) == [1, 2]
        assert len(observations) == 19
        assert all(
            run.observation_evidence_version == "calendar-observations-v1"
            for run in runs
        )
        assert all(revision.state == "current" for revision in revisions)
        assert EXCLUDED_CANARY not in "".join(revision.title for revision in revisions)
        assert not {
            "description",
            "location",
            "attendees",
            "organizer",
            "conference_data",
            "attachments",
            "reminders",
            "extended_properties",
            "provider_url",
        } & {
            column["name"]
            for column in inspect(get_engine()).get_columns("calendar_event_revisions")
        }
        protected_counts = {
            model.__tablename__: session.scalar(select(func.count(model.id)))
            for model in (Memory, MemoryProposal, AgentRun, Automation, Source)
        }
        output = tmp_path / "cp107-project-export.zip"
        export_project(
            session,
            uuid.UUID(project_a["id"]),
            output,
            source_alembic_revision=CURRENT_DATABASE_REVISION,
        )
    assert protected_counts == protected_before
    with zipfile.ZipFile(output) as archive:
        export_names = archive.namelist()
        export_bytes = b"".join(archive.read(name) for name in export_names)
    assert EXCLUDED_CANARY.encode() not in export_bytes
    assert HOSTILE.encode() not in export_bytes
    assert not any(name.startswith("calendar_") for name in export_names)

    revoked = client.post(
        f"/calendar-accounts/{account['id']}/revoke", json={"expected_revision": 1}
    )
    assert (
        revoked.status_code == 200
        and revoked.json()["account"]["lifecycle"] == "revoked"
    )
    calls = sum(len(transport.calls) for transport in transports)
    assert (
        client.post(
            f"/calendar-accounts/{account['id']}/refresh", json={"expected_revision": 2}
        ).status_code
        == 409
    )
    assert sum(len(transport.calls) for transport in transports) == calls
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count(CalendarEventRevision.id))) == 6
        assert session.scalar(select(func.count(CalendarEventObservation.id))) == 19


def test_unassigned_partial_unversioned_revision_drift_and_restart_fail_closed() -> (
    None
):
    client, _, transports = _client(
        [_events(), [_event("control", summary=CONTROL_CANARY)], []]
    )
    account = _create_account(client, None)
    first = client.post(
        f"/calendar-accounts/{account['id']}/refresh", json={"expected_revision": 1}
    ).json()[0]
    assert first["status"] == "succeeded"
    failed = client.post(
        f"/calendar-accounts/{account['id']}/refresh", json={"expected_revision": 1}
    ).json()[0]
    assert failed["status"] == "failed" and failed["completeness"] == "incomplete"
    assert all(
        item["effective_state"] == "current"
        for item in client.get(
            "/calendar-events", params={"scope": "unassigned"}
        ).json()["items"]
    )

    with Session(get_engine()) as session:
        failed_run = session.get(CalendarSyncRun, uuid.UUID(failed["id"]))
        assert (
            failed_run is not None and failed_run.observation_evidence_version is None
        )
        before = (
            session.scalar(select(func.count(CalendarEventRevision.id))),
            session.scalar(select(func.count(CalendarEventObservation.id))),
        )

    # A new app instance observes the committed safe state; retry remains explicit.
    app = create_app()
    boundary, _ = _authorized_boundary()
    app.dependency_overrides[calendar_credential_dependency] = lambda: boundary
    retry_transport = FakeCalendarTransport([CalendarPage([], None)])
    app.dependency_overrides[calendar_transport_factory_dependency] = lambda: (
        lambda: retry_transport
    )
    restarted = TestClient(app)
    assert (
        len(
            restarted.get("/calendar-events", params={"scope": "unassigned"}).json()[
                "items"
            ]
        )
        == 5
    )

    disabled = restarted.post(
        f"/calendar-accounts/{account['id']}/disable", json={"expected_revision": 1}
    ).json()
    assert disabled["configuration_revision"] == 2
    request_count = len(retry_transport.calls)
    assert (
        restarted.post(
            f"/calendar-accounts/{account['id']}/refresh", json={"expected_revision": 1}
        ).status_code
        == 409
    )
    assert len(retry_transport.calls) == request_count
    with Session(get_engine()) as session:
        after = (
            session.scalar(select(func.count(CalendarEventRevision.id))),
            session.scalar(select(func.count(CalendarEventObservation.id))),
        )
        assert after == before
        assert not set(session.scalars(select(CalendarEventRevision.state))) - {
            "current"
        }
    assert sum(len(transport.calls) for transport in transports) == 2
