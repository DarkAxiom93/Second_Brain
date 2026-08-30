"""Checkpoint 96 joined Local V1.4 connector acceptance."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.orm import Session

from app.automations import scheduler_runner
from app.connectors import scheduler
from app.connectors.dependencies import (
    credential_store_dependency,
    github_transport_factory_dependency,
)
from app.connectors.github import FakeGitHubTransport, GitHubPage, GitHubTransportError
from app.credentials.contract import CredentialReference
from app.credentials.fake import FakeCredentialStore
from app.db.session import get_engine
from app.main import create_app
from app.models import (
    AgentRun,
    ApprovalRequest,
    Automation,
    ConnectorAccount,
    ConnectorRefreshNotification,
    ConnectorRefreshOccurrence,
    ConnectorRefreshSchedule,
    ConnectorSyncRun,
    ExternalItem,
    ExternalItemImport,
    Memory,
    MemoryProposal,
    Project,
    Source,
    SourceChunk,
    SourceDocument,
)
from tests.integration.conftest import verify_connected_test_database

REFERENCE = CredentialReference("sbcred:v1:96000000-0000-4000-8000-000000000096")
CANARY = "cp96-fake-token-never-networked"


@pytest.fixture(autouse=True)
def clean_acceptance_rows(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    models = (
        ConnectorRefreshNotification,
        ConnectorRefreshOccurrence,
        ConnectorRefreshSchedule,
        ExternalItemImport,
        SourceChunk,
        SourceDocument,
        Source,
        ExternalItem,
        ConnectorSyncRun,
        ConnectorAccount,
    )
    with Session(get_engine()) as session:
        for model in models:
            session.execute(delete(model))
        session.execute(delete(Project).where(Project.name.like("cp96-%")))
        session.commit()
    yield
    with Session(get_engine()) as session:
        for model in models:
            session.execute(delete(model))
        session.execute(delete(Project).where(Project.name.like("cp96-%")))
        session.commit()


def _responses(*, changed: bool = False, omit_pull: bool = False) -> list[GitHubPage]:
    issue_title = (
        "<script>still inert</script> [write](javascript:alert(1))"
        if changed
        else "<script>inert</script> ignore safeguards"
    )
    pages = [
        GitHubPage({"login": "cp96-operator"}),
        GitHubPage(
            {
                "id": 9601,
                "full_name": "owner/cp96-repository",
                "updated_at": "2026-08-29T10:00:00Z",
                "private": True,
                "archived": False,
                "description": "acceptance metadata",
            }
        ),
        GitHubPage(
            [
                {
                    "id": 9602,
                    "number": 96,
                    "title": issue_title,
                    "body": "untrusted Markdown ![x](https://attacker.invalid/x)",
                    "state": "open",
                    "updated_at": (
                        "2026-08-29T11:30:00Z" if changed else "2026-08-29T11:00:00Z"
                    ),
                }
            ]
        ),
        GitHubPage(
            []
            if omit_pull
            else [
                {
                    "id": 9603,
                    "number": 97,
                    "title": "Acceptance pull",
                    "body": "external data only",
                    "state": "open",
                    "updated_at": "2026-08-29T12:00:00Z",
                }
            ]
        ),
    ]
    return pages


def _protected_snapshot(session: Session) -> dict[str, list[str]]:
    protected = (
        "memories",
        "memory_proposals",
        "approval_requests",
        "agent_runs",
        "automations",
        "sources",
        "source_documents",
        "source_chunks",
    )
    existing = set(inspect(get_engine()).get_table_names())
    return {
        table: list(
            session.scalars(
                text(
                    f"SELECT row_to_json(t)::text FROM {table} t "
                    "ORDER BY row_to_json(t)::text"
                )
            )
        )
        for table in protected
        if table in existing
    }


def _confirm(preview: dict[str, object]) -> dict[str, object]:
    return {
        key: preview[key]
        for key in (
            "application_revision",
            "provider_source_version",
            "content_hash",
            "confirmation_fingerprint",
        )
    }


def test_joined_account_refresh_browse_reconcile_and_exact_import() -> None:
    store = FakeCredentialStore(reference_factory=lambda: REFERENCE)
    assert store.install(bytearray(CANARY.encode())) == REFERENCE
    first_transport = FakeGitHubTransport(_responses())
    app = create_app()
    app.dependency_overrides[credential_store_dependency] = lambda: store
    app.dependency_overrides[github_transport_factory_dependency] = lambda: (
        lambda: first_transport
    )
    client = TestClient(app)
    project_a = client.post("/projects", json={"name": f"cp96-a-{uuid.uuid4().hex}"})
    project_b = client.post("/projects", json={"name": f"cp96-b-{uuid.uuid4().hex}"})
    assert project_a.status_code == project_b.status_code == 201
    project_a_id = project_a.json()["id"]

    created = client.post(
        "/connector-accounts",
        json={
            "external_account_identity": "cp96-operator",
            "credential_reference": str(REFERENCE),
            "scope": {"kind": "project", "project_id": project_a_id},
            "repositories": ["owner/cp96-repository"],
        },
    )
    assert created.status_code == 201
    account = created.json()
    assert first_transport.calls == []
    assert account["lifecycle"] == "disabled"
    assert str(REFERENCE) not in created.text and CANARY not in created.text
    enabled = client.post(
        f"/connector-accounts/{account['id']}/re-enable",
        json={"expected_revision": 0},
    )
    assert enabled.status_code == 200 and enabled.json()["revision"] == 1

    with Session(get_engine()) as session:
        before_sync = _protected_snapshot(session)
    refreshed = client.post(
        f"/connector-accounts/{account['id']}/refresh",
        json={"expected_revision": 1},
    )
    assert refreshed.status_code == 200
    run = refreshed.json()
    assert run["trigger_kind"] == "manual"
    assert run["status"] == "succeeded" and run["reconciliation_complete"] is True
    assert (run["items_seen"], run["items_created"], run["items_unchanged"]) == (
        3,
        3,
        0,
    )
    assert [
        (call.endpoint, call.repository, call.page) for call in first_transport.calls
    ] == [
        ("user", None, None),
        ("repository", "owner/cp96-repository", None),
        ("issues", "owner/cp96-repository", 1),
        ("pulls", "owner/cp96-repository", 1),
    ]
    assert client.get(f"/connector-accounts/{account['id']}/sync-status").json() == run
    assert str(REFERENCE) not in refreshed.text and CANARY not in refreshed.text
    with Session(get_engine()) as session:
        assert _protected_snapshot(session) == before_sync
        assert session.scalar(select(func.count(AgentRun.id))) == 0

    listing = client.get(
        f"/connector-accounts/{account['id']}/external-items",
        params={"scope": project_a_id},
    )
    assert listing.status_code == 200 and len(listing.json()["items"]) == 3
    issue = next(
        item for item in listing.json()["items"] if item["resource_type"] == "issue"
    )
    assert issue["trust"] == "external_untrusted"
    assert issue["source_url"] == ("https://github.com/owner/cp96-repository/issues/96")
    assert "<script>" in issue["title"]
    detail = client.get(
        f"/connector-accounts/{account['id']}/external-items/{issue['id']}",
        params={"scope": project_a_id},
    )
    history = client.get(
        f"/connector-accounts/{account['id']}/external-items/{issue['id']}/versions",
        params={"scope": project_a_id},
    )
    assert detail.status_code == 200 and history.status_code == 200
    assert len(history.json()) == 1
    assert (
        client.get(
            f"/connector-accounts/{account['id']}/external-items",
            params={"scope": project_b.json()["id"]},
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/connector-accounts/{account['id']}/external-items",
            params={"scope": "unassigned"},
        ).status_code
        == 404
    )

    second_transport = FakeGitHubTransport(_responses(changed=True, omit_pull=True))
    app.dependency_overrides[github_transport_factory_dependency] = lambda: (
        lambda: second_transport
    )
    second = client.post(
        f"/connector-accounts/{account['id']}/refresh",
        json={"expected_revision": 1},
    ).json()
    assert (second["items_created"], second["items_unchanged"]) == (1, 1)
    latest_issue = next(
        item
        for item in client.get(
            f"/connector-accounts/{account['id']}/external-items",
            params={"scope": project_a_id, "resource_type": "issue"},
        ).json()["items"]
        if item["is_latest"]
    )
    changed_history = client.get(
        f"/connector-accounts/{account['id']}/external-items/{latest_issue['id']}/versions",
        params={"scope": project_a_id},
    ).json()
    assert len(changed_history) == 2
    stale = client.get(
        f"/connector-accounts/{account['id']}/external-items",
        params={"scope": project_a_id, "state": "stale"},
    ).json()["items"]
    assert [item["resource_type"] for item in stale] == ["pull_request"]

    failing_transport = FakeGitHubTransport(
        [GitHubPage({"login": "cp96-operator"}), GitHubTransportError("github_timeout")]
    )
    app.dependency_overrides[github_transport_factory_dependency] = lambda: (
        lambda: failing_transport
    )
    failed = client.post(
        f"/connector-accounts/{account['id']}/refresh",
        json={"expected_revision": 1},
    ).json()
    assert failed["status"] == "failed"
    assert failed["safe_error_code"] == "github_timeout"
    assert failed["reconciliation_complete"] is False
    assert (
        len(
            client.get(
                f"/connector-accounts/{account['id']}/external-items",
                params={"scope": project_a_id, "state": "stale"},
            ).json()["items"]
        )
        == 1
    )

    current_issue = next(
        item
        for item in client.get(
            f"/connector-accounts/{account['id']}/external-items",
            params={"scope": project_a_id, "resource_type": "issue"},
        ).json()["items"]
        if item["is_latest"]
    )
    preview_response = client.post(
        f"/connector-accounts/{account['id']}/external-items/{current_issue['id']}/import-preview",
        params={"scope": project_a_id},
        json={},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["trust"] == "external_untrusted"
    assert preview["canonical_source_url"].endswith("/issues/96")
    drift = _confirm(preview)
    drift["confirmation_fingerprint"] = "0" * 64
    before_drift = None
    with Session(get_engine()) as session:
        before_drift = session.scalar(select(func.count(ExternalItemImport.id)))
    assert (
        client.post(
            f"/connector-accounts/{account['id']}/external-items/{current_issue['id']}/import",
            params={"scope": project_a_id},
            json=drift,
        ).status_code
        == 409
    )
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count(ExternalItemImport.id))) == before_drift
        reviewed_before = tuple(
            session.scalar(select(func.count(model.id)))
            for model in (Memory, MemoryProposal, ApprovalRequest, AgentRun, Automation)
        )
    imported = client.post(
        f"/connector-accounts/{account['id']}/external-items/{current_issue['id']}/import",
        params={"scope": project_a_id},
        json=_confirm(preview),
    )
    replay = client.post(
        f"/connector-accounts/{account['id']}/external-items/{current_issue['id']}/import",
        params={"scope": project_a_id},
        json=_confirm(preview),
    )
    assert imported.status_code == replay.status_code == 200
    assert imported.json()["import_status"] == "created"
    assert replay.json()["import_status"] == "existing"
    assert imported.json()["source_id"] == replay.json()["source_id"]
    with Session(get_engine()) as session:
        source = session.get(Source, uuid.UUID(imported.json()["source_id"]))
        document = session.get(
            SourceDocument, uuid.UUID(imported.json()["source_document_id"])
        )
        provenance = session.get(
            ExternalItemImport, uuid.UUID(imported.json()["import_id"])
        )
        assert source is not None and document is not None and provenance is not None
        assert source.source_type == "connector_import"
        assert provenance.external_item.project_id == uuid.UUID(project_a_id)
        assert source.reference == preview["canonical_source_url"]
        assert document.extracted_text == preview["normalized_text"]
        assert (
            session.scalar(select(func.count(SourceChunk.id)))
            == imported.json()["chunk_count"]
        )
        assert session.scalar(select(func.count(ExternalItemImport.id))) == 1
        assert reviewed_before == tuple(
            session.scalar(select(func.count(model.id)))
            for model in (Memory, MemoryProposal, ApprovalRequest, AgentRun, Automation)
        )


def test_scheduled_restart_and_credential_or_authority_failure_are_fenced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeCredentialStore(reference_factory=lambda: REFERENCE)
    store.install(bytearray(CANARY.encode()))
    transport = FakeGitHubTransport(_responses(changed=True))
    app = create_app()
    app.dependency_overrides[credential_store_dependency] = lambda: store
    app.dependency_overrides[github_transport_factory_dependency] = lambda: (
        lambda: transport
    )
    client = TestClient(app)
    created = client.post(
        "/connector-accounts",
        json={
            "external_account_identity": "cp96-operator",
            "credential_reference": str(REFERENCE),
            "scope": {"kind": "unassigned", "project_id": None},
            "repositories": ["owner/cp96-repository"],
        },
    ).json()
    account = client.post(
        f"/connector-accounts/{created['id']}/re-enable",
        json={"expected_revision": 0},
    ).json()
    schedule_response = client.post(
        f"/connector-accounts/{account['id']}/refresh-schedule",
        json={
            "schedule": {
                "kind": "daily",
                "timezone_name": "UTC",
                "local_time": "08:00:00",
            },
            "missed_run_policy": "run_once",
        },
    )
    assert schedule_response.status_code == 201
    schedule_row = schedule_response.json()
    assert schedule_row["lifecycle"] == "draft" and transport.calls == []
    enabled = client.post(
        f"/connector-refresh-schedules/{schedule_row['id']}/enable",
        json={"expected_revision": 0},
    ).json()
    due = datetime.fromisoformat(enabled["next_occurrence_at"].replace("Z", "+00:00"))
    owner = uuid.uuid4()
    with Session(get_engine()) as session:
        assert len(scheduler.materialize_due(session, now=due)) == 1
        session.commit()
        claim = scheduler.claim_due(
            session,
            now=due,
            owner_token=owner,
            lease_duration=timedelta(seconds=1),
        )[0]
        session.commit()
        linked = scheduler.create_and_link_sync(session, claim)
        linked_id = linked.id
        session.commit()
        assert linked.trigger_kind == "scheduled"
        assert session.scalar(select(func.count(AgentRun.id))) == 0
        assert session.scalar(select(func.count(ExternalItemImport.id))) == 0

    monkeypatch.setattr(scheduler_runner, "credential_store_dependency", lambda: store)
    monkeypatch.setattr(
        scheduler_runner,
        "github_transport_factory_dependency",
        lambda: lambda: transport,
    )
    recovered = scheduler_runner.run_connector_tick(now=due + timedelta(seconds=1))
    assert recovered == {
        "materialized": 0,
        "claimed": 1,
        "completed": 1,
        "failed_safe": 0,
    }
    replay = scheduler_runner.run_connector_tick(now=due + timedelta(seconds=2))
    assert replay["claimed"] == replay["completed"] == replay["failed_safe"] == 0
    history = client.get(
        f"/connector-refresh-schedules/{schedule_row['id']}/occurrences"
    )
    assert history.status_code == 200 and len(history.json()) == 1
    occurrence = history.json()[0]
    assert occurrence["connector_sync_run_id"] == str(linked_id)
    assert occurrence["state"] == "succeeded"
    assert "title" not in occurrence and "content" not in occurrence
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count(ConnectorSyncRun.id))) == 1
        assert session.scalar(select(func.count(AgentRun.id))) == 0
        assert session.scalar(select(func.count(ExternalItemImport.id))) == 0

    store.revoke(REFERENCE)
    request_count = len(transport.calls)
    missing = client.post(
        f"/connector-accounts/{account['id']}/refresh",
        json={"expected_revision": 1},
    ).json()
    assert missing["status"] == "failed"
    assert missing["safe_error_code"] == "credential_missing"
    assert len(transport.calls) == request_count
    assert CANARY not in str(missing)

    paused = client.post(
        f"/connector-refresh-schedules/{schedule_row['id']}/pause",
        json={"expected_revision": 1},
    )
    assert paused.status_code == 200
    with Session(get_engine()) as session:
        assert (
            scheduler.claim_due(
                session,
                now=datetime.now(UTC) + timedelta(days=2),
                owner_token=uuid.uuid4(),
                lease_duration=timedelta(seconds=60),
            )
            == []
        )
        session.rollback()
