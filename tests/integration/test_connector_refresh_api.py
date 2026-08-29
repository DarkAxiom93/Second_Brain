"""Checkpoint 91 manual GitHub refresh acceptance with fakes only."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.orm import Session

from app.connectors.dependencies import (
    credential_store_dependency,
    github_transport_factory_dependency,
)
from app.connectors.github import FakeGitHubTransport, GitHubPage, GitHubTransportError
from app.credentials.contract import (
    CredentialReference,
    CredentialStoreError,
    CredentialStoreLockedError,
    CredentialStoreMissingError,
    CredentialStoreUnavailableError,
)
from app.credentials.fake import FakeCredentialStore
from app.db.session import get_engine
from app.main import create_app
from app.models.connector import ConnectorAccount, ConnectorSyncRun, ExternalItem
from tests.integration.conftest import verify_connected_test_database

REFERENCE = CredentialReference("sbcred:v1:12345678-1234-4123-8123-123456789abc")


class TrackingCredentialStore(FakeCredentialStore):
    returned_secret: bytearray | None = None

    def read(self, reference: CredentialReference) -> bytearray:
        self.returned_secret = super().read(reference)
        return self.returned_secret


@pytest.fixture(autouse=True)
def clean_connectors(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(ExternalItem))
        session.execute(delete(ConnectorSyncRun))
        session.execute(delete(ConnectorAccount))
        session.commit()
    yield
    with Session(get_engine()) as session:
        session.execute(delete(ExternalItem))
        session.execute(delete(ConnectorSyncRun))
        session.execute(delete(ConnectorAccount))
        session.commit()


def _store() -> FakeCredentialStore:
    store = FakeCredentialStore(reference_factory=lambda: REFERENCE)
    assert store.install(bytearray(b"fake-token-never-networked")) == REFERENCE
    return store


def _responses(login: str = "operator-account") -> list[GitHubPage]:
    return [
        GitHubPage({"login": login}),
        GitHubPage(
            {
                "id": 101,
                "full_name": "owner/repository",
                "updated_at": "2026-08-28T10:00:00Z",
                "private": True,
                "archived": False,
                "description": "private metadata",
            }
        ),
        GitHubPage(
            [
                {
                    "id": 201,
                    "number": 1,
                    "title": "Issue title",
                    "body": "<script>inert()</script>",
                    "state": "open",
                    "updated_at": "2026-08-28T11:00:00Z",
                },
                {
                    "id": 202,
                    "number": 2,
                    "title": "PR excluded from issues",
                    "body": "ignored",
                    "state": "open",
                    "updated_at": "2026-08-28T11:00:00Z",
                    "pull_request": {},
                },
            ]
        ),
        GitHubPage(
            [
                {
                    "id": 202,
                    "number": 2,
                    "title": "Pull title",
                    "body": "untrusted markdown",
                    "state": "open",
                    "updated_at": "2026-08-28T12:00:00Z",
                }
            ]
        ),
    ]


def _protected_snapshots(session: Session) -> dict[str, list[str]]:
    excluded = {
        "alembic_version",
        "connector_accounts",
        "connector_sync_runs",
        "external_items",
    }
    return {
        table: list(
            session.scalars(
                text(
                    f"SELECT row_to_json(t)::text FROM {table} t "
                    "ORDER BY row_to_json(t)::text"
                )
            )
        )
        for table in inspect(get_engine()).get_table_names()
        if table not in excluded
    }


def _enabled_client(transport: FakeGitHubTransport) -> tuple[TestClient, str]:
    app = create_app()
    store = _store()
    app.dependency_overrides[credential_store_dependency] = lambda: store
    app.dependency_overrides[github_transport_factory_dependency] = lambda: (
        lambda: transport
    )
    client = TestClient(app)
    created = client.post(
        "/connector-accounts",
        json={
            "external_account_identity": "operator-account",
            "credential_reference": str(REFERENCE),
            "scope": {"kind": "unassigned", "project_id": None},
            "repositories": ["owner/repository"],
        },
    ).json()
    enabled = client.post(
        f"/connector-accounts/{created['id']}/re-enable",
        json={"expected_revision": 0},
    ).json()
    assert enabled["revision"] == 1
    return client, created["id"]


def test_manual_refresh_inventory_quarantine_replay_and_safe_status() -> None:
    first_transport = FakeGitHubTransport(_responses())
    client, account_id = _enabled_client(first_transport)
    with Session(get_engine()) as session:
        protected_before = _protected_snapshots(session)
    response = client.post(
        f"/connector-accounts/{account_id}/refresh",
        json={"expected_revision": 1},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "succeeded"
    assert result["reconciliation_complete"] is True
    assert (
        result["items_seen"],
        result["items_created"],
        result["items_unchanged"],
    ) == (3, 3, 0)
    assert [
        (call.endpoint, call.repository, call.page) for call in first_transport.calls
    ] == [
        ("user", None, None),
        ("repository", "owner/repository", None),
        ("issues", "owner/repository", 1),
        ("pulls", "owner/repository", 1),
    ]
    latest = client.get(f"/connector-accounts/{account_id}/sync-status")
    assert latest.json() == result
    account = client.get(f"/connector-accounts/{account_id}").json()
    assert account["validation_status"] == "valid"
    assert account["revision"] == 1
    assert "fake-token" not in response.text
    with Session(get_engine()) as session:
        items = list(session.scalars(select(ExternalItem)))
        assert {item.resource_type for item in items} == {
            "repository",
            "issue",
            "pull_request",
        }
        assert all(item.state == "current" for item in items)
        assert _protected_snapshots(session) == protected_before

    replay_transport = FakeGitHubTransport(_responses())
    client.app.dependency_overrides[github_transport_factory_dependency] = lambda: (
        lambda: replay_transport
    )
    replay = client.post(
        f"/connector-accounts/{account_id}/refresh",
        json={"expected_revision": 1},
    ).json()
    assert (replay["items_created"], replay["items_unchanged"]) == (0, 3)
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count(ExternalItem.id))) == 3


def test_disabled_and_stale_revision_make_zero_requests() -> None:
    transport = FakeGitHubTransport([])
    app = create_app()
    app.dependency_overrides[credential_store_dependency] = _store
    app.dependency_overrides[github_transport_factory_dependency] = lambda: (
        lambda: transport
    )
    client = TestClient(app)
    created = client.post(
        "/connector-accounts",
        json={
            "external_account_identity": "operator-account",
            "credential_reference": str(REFERENCE),
            "scope": {"kind": "unassigned", "project_id": None},
            "repositories": ["owner/repository"],
        },
    ).json()
    assert (
        client.post(
            f"/connector-accounts/{created['id']}/refresh",
            json={"expected_revision": 0},
        ).status_code
        == 409
    )
    client.post(
        f"/connector-accounts/{created['id']}/re-enable",
        json={"expected_revision": 0},
    )
    assert (
        client.post(
            f"/connector-accounts/{created['id']}/refresh",
            json={"expected_revision": 0},
        ).status_code
        == 409
    )
    assert transport.calls == []


def test_authenticated_identity_mismatch_fails_and_fences_account() -> None:
    transport = FakeGitHubTransport(_responses("different-account")[:1])
    client, account_id = _enabled_client(transport)
    result = client.post(
        f"/connector-accounts/{account_id}/refresh",
        json={"expected_revision": 1},
    ).json()
    assert result["status"] == "failed"
    assert result["safe_error_code"] == "github_identity_mismatch"
    account = client.get(f"/connector-accounts/{account_id}").json()
    assert (
        account["lifecycle"],
        account["validation_status"],
        account["revision"],
    ) == (
        "disabled",
        "invalid",
        2,
    )
    assert [call.endpoint for call in transport.calls] == ["user"]


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (CredentialStoreMissingError(), "credential_missing"),
        (CredentialStoreLockedError(), "credential_store_locked"),
        (CredentialStoreUnavailableError(), "credential_store_unavailable"),
    ],
)
def test_credential_failures_are_safe_and_make_zero_requests(
    failure: CredentialStoreError, code: str
) -> None:
    transport = FakeGitHubTransport([])
    client, account_id = _enabled_client(transport)
    failed_store = FakeCredentialStore(
        reference_factory=lambda: REFERENCE, failure=failure
    )
    client.app.dependency_overrides[credential_store_dependency] = lambda: failed_store
    result = client.post(
        f"/connector-accounts/{account_id}/refresh",
        json={"expected_revision": 1},
    ).json()
    assert (result["status"], result["safe_error_code"]) == ("failed", code)
    assert transport.calls == []
    assert str(REFERENCE) not in str(result)


def test_page_failure_preserves_earlier_quarantine_and_is_not_complete() -> None:
    responses = _responses()[:2]
    responses.extend(
        [
            GitHubPage(
                [
                    {
                        "id": 201,
                        "number": 1,
                        "title": "Committed issue",
                        "body": "untrusted",
                        "state": "open",
                        "updated_at": "2026-08-28T11:00:00Z",
                    }
                ]
            ),
            GitHubPage({"malformed": True}),
        ]
    )
    client, account_id = _enabled_client(FakeGitHubTransport(responses))
    result = client.post(
        f"/connector-accounts/{account_id}/refresh",
        json={"expected_revision": 1},
    ).json()
    assert (result["status"], result["safe_error_code"]) == (
        "failed",
        "github_invalid_response",
    )
    assert result["reconciliation_complete"] is False
    with Session(get_engine()) as session:
        items = list(session.scalars(select(ExternalItem)))
        assert {item.resource_type for item in items} == {"repository", "issue"}
        assert all(item.state == "current" for item in items)


def test_pagination_ceiling_is_incomplete_without_deletion_inference() -> None:
    def issue(index: int) -> dict[str, object]:
        return {
            "id": 1_000 + index,
            "number": index + 1,
            "title": f"Issue {index}",
            "body": "bounded",
            "state": "open",
            "updated_at": "2026-08-28T11:00:00Z",
        }

    responses = _responses()[:2]
    responses.extend(
        [
            GitHubPage([issue(index) for index in range(50)], may_have_more=True),
            GitHubPage([issue(index) for index in range(50, 100)], may_have_more=True),
            GitHubPage([]),
        ]
    )
    client, account_id = _enabled_client(FakeGitHubTransport(responses))
    result = client.post(
        f"/connector-accounts/{account_id}/refresh",
        json={"expected_revision": 1},
    ).json()
    assert (result["status"], result["safe_error_code"]) == (
        "incomplete",
        "github_pagination_ceiling",
    )
    assert result["reconciliation_complete"] is False
    assert result["items_seen"] == 101
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count(ExternalItem.id))) == 101
        assert not session.scalar(
            select(func.count(ExternalItem.id)).where(ExternalItem.state != "current")
        )


def test_repository_numeric_identity_change_is_rejected() -> None:
    client, account_id = _enabled_client(FakeGitHubTransport(_responses()))
    assert (
        client.post(
            f"/connector-accounts/{account_id}/refresh", json={"expected_revision": 1}
        ).json()["status"]
        == "succeeded"
    )
    changed = _responses()
    repository_response = changed[1].value
    assert isinstance(repository_response, dict)
    repository_response["id"] = 999
    client.app.dependency_overrides[github_transport_factory_dependency] = lambda: (
        lambda: FakeGitHubTransport(changed)
    )
    result = client.post(
        f"/connector-accounts/{account_id}/refresh", json={"expected_revision": 1}
    ).json()
    assert result["safe_error_code"] == "github_identity_mismatch"
    with Session(get_engine()) as session:
        repository_ids = set(
            session.scalars(
                select(ExternalItem.external_resource_id).where(
                    ExternalItem.resource_type == "repository"
                )
            )
        )
        assert repository_ids == {"github_repo:101"}


def test_transient_secret_buffer_is_cleared_after_refresh() -> None:
    transport = FakeGitHubTransport(_responses())
    client, account_id = _enabled_client(transport)
    store = TrackingCredentialStore(reference_factory=lambda: REFERENCE)
    store.install(bytearray(b"fake-cleanup-canary"))
    client.app.dependency_overrides[credential_store_dependency] = lambda: store
    assert (
        client.post(
            f"/connector-accounts/{account_id}/refresh", json={"expected_revision": 1}
        ).status_code
        == 200
    )
    assert store.returned_secret is not None
    assert store.returned_secret == bytearray(len(store.returned_secret))


def test_global_active_sync_cap_rejects_before_credential_or_network() -> None:
    app = create_app()
    transport = FakeGitHubTransport([])
    app.dependency_overrides[credential_store_dependency] = _store
    app.dependency_overrides[github_transport_factory_dependency] = lambda: (
        lambda: transport
    )
    client = TestClient(app)
    accounts: list[dict[str, object]] = []
    for index in range(5):
        created = client.post(
            "/connector-accounts",
            json={
                "external_account_identity": f"operator-{index}",
                "credential_reference": (
                    f"sbcred:v1:12345678-1234-4123-8123-{index:012d}"
                ),
                "scope": {"kind": "unassigned", "project_id": None},
                "repositories": ["owner/repository"],
            },
        ).json()
        accounts.append(
            client.post(
                f"/connector-accounts/{created['id']}/re-enable",
                json={"expected_revision": 0},
            ).json()
        )
    with Session(get_engine()) as session:
        for value in accounts[:4]:
            account = session.get(ConnectorAccount, uuid.UUID(str(value["id"])))
            assert account is not None
            session.add(
                ConnectorSyncRun(
                    account_id=account.id,
                    provider="github",
                    external_account_id=account.external_account_id,
                    account_revision=account.revision,
                    project_id=account.project_id,
                    trigger_kind="manual",
                    trigger_identity="operator_manual_refresh",
                    status="claimed",
                )
            )
        session.commit()
    fifth = accounts[4]
    response = client.post(
        f"/connector-accounts/{fifth['id']}/refresh",
        json={"expected_revision": fifth["revision"]},
    )
    assert response.status_code == 409
    assert transport.calls == []
    with Session(get_engine()) as session:
        assert (
            session.scalar(
                select(func.count(ConnectorSyncRun.id)).where(
                    ConnectorSyncRun.status.in_(("claimed", "running"))
                )
            )
            == 4
        )


@pytest.mark.parametrize(
    "code",
    ["github_rate_limited", "github_timeout", "github_unavailable"],
)
def test_provider_failures_return_only_safe_explicit_retry_status(code: str) -> None:
    transport = FakeGitHubTransport(
        [GitHubPage({"login": "operator-account"}), GitHubTransportError(code)]
    )
    client, account_id = _enabled_client(transport)
    result = client.post(
        f"/connector-accounts/{account_id}/refresh", json={"expected_revision": 1}
    ).json()
    assert result["status"] == "failed"
    assert result["safe_error_code"] == code
    assert result["reconciliation_complete"] is False
    assert len(transport.calls) == 2
