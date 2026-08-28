"""Checkpoint 90 metadata-only connector account API acceptance."""

import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.main import create_app
from app.models.connector import ConnectorAccount, ConnectorSyncRun, ExternalItem
from app.models.project import Project
from tests.integration.conftest import verify_connected_test_database


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


def _payload(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "external_account_identity": "operator-account",
        "credential_reference": "sbcred:v1:12345678-1234-4123-8123-123456789abc",
        "scope": {"kind": "unassigned", "project_id": None},
        "repositories": ["owner/repository"],
    }
    values.update(changes)
    return values


def test_create_list_retrieve_is_safe_disabled_unvalidated_and_github() -> None:
    client = TestClient(create_app())
    response = client.post("/connector-accounts", json=_payload())
    assert response.status_code == 201
    created = response.json()
    assert (
        created["provider"],
        created["lifecycle"],
        created["validation_status"],
    ) == (
        "github",
        "disabled",
        "unvalidated",
    )
    assert created["scope"] == {"kind": "unassigned", "project_id": None}
    forbidden = {
        "credential_reference",
        "external_account_fingerprint",
        "granted_scope_fingerprint",
    }
    assert forbidden.isdisjoint(created)
    assert "sbcred:" not in response.text
    assert client.get(f"/connector-accounts/{created['id']}").json() == created
    assert client.get("/connector-accounts").json() == [created]


def test_exact_project_or_explicit_unassigned_and_closed_input() -> None:
    client = TestClient(create_app())
    with Session(get_engine()) as session:
        project = Project(name="connector-project-" + uuid.uuid4().hex)
        session.add(project)
        session.commit()
        project_id = str(project.id)
    assigned = client.post(
        "/connector-accounts",
        json=_payload(scope={"kind": "project", "project_id": project_id}),
    )
    assert assigned.status_code == 201
    assert assigned.json()["scope"] == {"kind": "project", "project_id": project_id}
    bad_scopes = [
        {"kind": "project", "project_id": None},
        {"kind": "unassigned", "project_id": project_id},
        {"kind": "project", "project_id": str(uuid.uuid4())},
    ]
    for index, scope in enumerate(bad_scopes):
        result = client.post(
            "/connector-accounts",
            json=_payload(
                external_account_identity=f"other-{index}",
                credential_reference=f"sbcred:v1:12345678-1234-4123-8123-{index:012d}",
                scope=scope,
            ),
        )
        assert result.status_code in {404, 422}
    unknown = _payload(provider="github", lifecycle="enabled", revision=9)
    assert client.post("/connector-accounts", json=unknown).status_code == 422


@pytest.mark.parametrize(
    "changes",
    [
        {"repositories": []},
        {"repositories": [f"owner/repo-{index}" for index in range(33)]},
        {"repositories": ["owner/repo", "OWNER/REPO"]},
        {"repositories": ["owner/repo/extra"]},
        {"repositories": ["https://github.com/owner/repo"]},
        {"external_account_identity": "github_pat_secret"},
        {"credential_reference": "github_pat_secret"},
    ],
)
def test_allowlist_bounds_canonical_validation_and_hostile_input(
    changes: dict[str, object],
) -> None:
    response = TestClient(create_app()).post(
        "/connector-accounts", json=_payload(**changes)
    )
    assert response.status_code == 422
    assert "github_pat_secret" not in response.text


def test_revision_lifecycle_matrix_terminal_revoke_and_configuration_rule() -> None:
    client = TestClient(create_app())
    created = client.post("/connector-accounts", json=_payload()).json()
    account_id = created["id"]
    enabled = client.post(
        f"/connector-accounts/{account_id}/re-enable",
        json={"expected_revision": 0},
    ).json()
    assert (enabled["lifecycle"], enabled["revision"]) == ("enabled", 1)
    assert (
        client.patch(
            f"/connector-accounts/{account_id}",
            json={"expected_revision": 1, "repositories": ["owner/changed"]},
        ).status_code
        == 409
    )
    stale = client.post(
        f"/connector-accounts/{account_id}/disable",
        json={"expected_revision": 0},
    )
    assert stale.status_code == 409
    disabled = client.post(
        f"/connector-accounts/{account_id}/disable",
        json={"expected_revision": 1},
    ).json()
    updated = client.patch(
        f"/connector-accounts/{account_id}",
        json={"expected_revision": 2, "repositories": ["owner/changed"]},
    ).json()
    assert (disabled["revision"], updated["revision"]) == (2, 3)
    assert updated["validation_status"] == "unvalidated"
    revoked = client.post(
        f"/connector-accounts/{account_id}/revoke",
        json={"expected_revision": 3},
    ).json()
    assert (
        revoked["lifecycle"],
        revoked["validation_status"],
        revoked["revision"],
    ) == (
        "revoked",
        "revoked",
        4,
    )
    for action in ("disable", "re-enable", "revoke"):
        assert (
            client.post(
                f"/connector-accounts/{account_id}/{action}",
                json={"expected_revision": 4},
            ).status_code
            == 409
        )


def test_no_sync_or_protected_domain_creation_and_no_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import socket

    def forbidden_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("Checkpoint 90 must not use network")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    client = TestClient(create_app())
    with Session(get_engine()) as session:
        table_names = (
            "sources",
            "source_documents",
            "memory_proposals",
            "memories",
            "approval_requests",
            "agent_runs",
            "automations",
        )
        # Use stable SQL counts without loading or mutating protected ORM domains.
        before = {
            name: session.execute(text(f"SELECT count(*) FROM {name}")).scalar_one()
            for name in table_names
        }
    assert client.post("/connector-accounts", json=_payload()).status_code == 201
    with Session(get_engine()) as session:
        after = {
            name: session.execute(text(f"SELECT count(*) FROM {name}")).scalar_one()
            for name in table_names
        }
        assert before == after
        assert session.scalar(select(func.count(ConnectorSyncRun.id))) == 0
        assert session.scalar(select(func.count(ExternalItem.id))) == 0


def test_row_lock_serializes_revision_and_active_sync_fences_configuration() -> None:
    client = TestClient(create_app())
    created = client.post("/connector-accounts", json=_payload()).json()

    def enable() -> int:
        return (
            TestClient(create_app())
            .post(
                f"/connector-accounts/{created['id']}/re-enable",
                json={"expected_revision": 0},
            )
            .status_code
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: enable(), range(2))) == [200, 409]

    current = client.get(f"/connector-accounts/{created['id']}").json()
    disabled = client.post(
        f"/connector-accounts/{created['id']}/disable",
        json={"expected_revision": current["revision"]},
    ).json()
    with Session(get_engine()) as session:
        account = session.get(ConnectorAccount, uuid.UUID(created["id"]))
        assert account is not None
        session.add(
            ConnectorSyncRun(
                account_id=account.id,
                provider=account.provider,
                external_account_id=account.external_account_id,
                account_revision=account.revision,
                project_id=account.project_id,
                trigger_kind="manual",
                trigger_identity="preexisting_claim",
                status="claimed",
                created_at=datetime.now(UTC),
            )
        )
        session.commit()
    assert (
        client.patch(
            f"/connector-accounts/{created['id']}",
            json={
                "expected_revision": disabled["revision"],
                "repositories": ["owner/changed"],
            },
        ).status_code
        == 409
    )
