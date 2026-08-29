"""Explicit synchronous, bounded, quarantine-only GitHub refresh."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.connectors.github import GitHubPage, GitHubTransport, GitHubTransportError
from app.connectors.service import _APPLICATION_READ_POLICY, _external_fingerprint
from app.connectors.validation import (
    granted_scope_fingerprint,
    snapshot_content_hash,
    validate_account_values,
    validate_item_values,
)
from app.credentials.contract import (
    CredentialStore,
    CredentialStoreError,
    clear_secret,
    validate_credential_reference,
)
from app.models.connector import ConnectorAccount, ConnectorSyncRun, ExternalItem
from app.repositories import connectors as repository
from app.schemas.connector import ConnectorSyncRunRead, SyncStatus

GLOBAL_ACTIVE_SYNC_CAP = 4
MAX_ACCEPTED_ITEMS = 2_000
MAX_DATA_PAGES = 2
SYNC_WALL_CLOCK_SECONDS = 60.0
_TRIGGER_IDENTITY = "operator_manual_refresh"
_CEILING_CODES = {
    "github_pagination_ceiling",
    "github_item_ceiling",
    "github_request_ceiling",
    "github_deadline_ceiling",
    "github_run_byte_ceiling",
}
_IDENTITY_FAILURES = {
    "github_unauthorized",
    "github_forbidden",
    "github_not_found",
    "github_identity_mismatch",
}


class SyncNotFoundError(Exception):
    pass


class SyncConflictError(Exception):
    pass


class SyncRevisionConflictError(Exception):
    pass


class SyncCapacityConflictError(Exception):
    pass


def public_sync_run(run: ConnectorSyncRun) -> ConnectorSyncRunRead:
    return ConnectorSyncRunRead(
        id=run.id,
        account_id=run.account_id,
        account_revision=run.account_revision,
        trigger_kind="manual",
        status=cast(SyncStatus, run.status),
        items_seen=run.items_seen,
        items_created=run.items_created,
        items_unchanged=run.items_unchanged,
        safe_error_code=run.safe_error_code,
        reconciliation_complete=run.reconciliation_complete,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def claim(
    session: Session, account_id: uuid.UUID, expected_revision: int
) -> ConnectorSyncRun:
    repository.lock_sync_capacity(session)
    account = repository.lock_account(session, account_id)
    if account is None:
        raise SyncNotFoundError
    if account.revision != expected_revision:
        raise SyncRevisionConflictError
    if account.lifecycle != "enabled":
        raise SyncConflictError
    try:
        validate_account_values(
            provider=account.provider,
            external_account_id=account.external_account_id,
            external_account_fingerprint=account.external_account_fingerprint,
            credential_reference=account.credential_reference,
            resource_allowlist=account.resource_allowlist,
            granted_scope_fingerprint=account.granted_scope_fingerprint,
        )
    except ValueError:
        raise SyncConflictError from None
    if (
        account.external_account_fingerprint
        != _external_fingerprint(account.external_account_id)
        or account.granted_scope_fingerprint
        != granted_scope_fingerprint(_APPLICATION_READ_POLICY)
        or len({value.casefold() for value in account.resource_allowlist})
        != len(account.resource_allowlist)
    ):
        raise SyncConflictError
    if repository.has_active_sync_run(session, account.id):
        raise SyncConflictError
    if repository.active_sync_count(session) >= GLOBAL_ACTIVE_SYNC_CAP:
        raise SyncCapacityConflictError
    run = ConnectorSyncRun(
        account_id=account.id,
        provider=account.provider,
        external_account_id=account.external_account_id,
        account_revision=account.revision,
        project_id=account.project_id,
        trigger_kind="manual",
        trigger_identity=_TRIGGER_IDENTITY,
        status="claimed",
    )
    try:
        return repository.create_sync_run(session, run)
    except IntegrityError:
        raise SyncConflictError from None


def _captured_account(session: Session, run: ConnectorSyncRun) -> ConnectorAccount:
    account = repository.get_account(session, run.account_id)
    if (
        account is None
        or account.lifecycle != "enabled"
        or account.revision != run.account_revision
        or account.project_id != run.project_id
        or account.provider != "github"
        or account.external_account_id != run.external_account_id
        or account.external_account_fingerprint
        != _external_fingerprint(account.external_account_id)
        or account.granted_scope_fingerprint
        != granted_scope_fingerprint(_APPLICATION_READ_POLICY)
    ):
        raise GitHubTransportError("account_revision_drift")
    return account


def _required_dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GitHubTransportError("github_invalid_response")
    return value


def _integer(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise GitHubTransportError("github_invalid_response")
    return value


def _string(value: object, *, optional: bool = False) -> str:
    if optional and value is None:
        return ""
    if not isinstance(value, str):
        raise GitHubTransportError("github_invalid_response")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise GitHubTransportError("github_invalid_response") from None
    return value


def _github_timestamp(value: object) -> str:
    timestamp = _string(value)
    try:
        parsed = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        raise GitHubTransportError("github_invalid_response") from None
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _validated_snapshot(
    *,
    repo_id: int,
    item_id: str,
    resource_type: str,
    version: str,
    title: str,
    body: str,
) -> tuple[str, str, str, str]:
    content_hash = snapshot_content_hash(title, body)
    try:
        validate_item_values(
            provider="github",
            resource_type=resource_type,
            external_resource_id=f"github_repo:{repo_id}",
            external_item_id=item_id,
            provider_source_version=version,
            title=title,
            body=body,
            content_hash=content_hash,
        )
    except ValueError as exc:
        if "exceeds limit" in str(exc):
            raise GitHubTransportError("github_item_oversized") from None
        raise GitHubTransportError("github_invalid_response") from None
    return item_id, title, body, version


def _repository_snapshot(data: object, expected: str) -> tuple[int, str, str, str]:
    value = _required_dict(data)
    repo_id = _integer(value.get("id"))
    full_name = _string(value.get("full_name"))
    if full_name.casefold() != expected.casefold():
        raise GitHubTransportError("github_identity_mismatch")
    updated_at = _github_timestamp(value.get("updated_at"))
    normalized = {
        "archived": value.get("archived"),
        "description": value.get("description"),
        "private": value.get("private"),
    }
    if not isinstance(normalized["archived"], bool) or not isinstance(
        normalized["private"], bool
    ):
        raise GitHubTransportError("github_invalid_response")
    if normalized["description"] is not None and not isinstance(
        normalized["description"], str
    ):
        raise GitHubTransportError("github_invalid_response")
    body = json.dumps(
        normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    snapshot = _validated_snapshot(
        repo_id=repo_id,
        item_id=f"github_repo:{repo_id}",
        resource_type="repository",
        version=f"{updated_at}:{repo_id}",
        title=full_name,
        body=body,
    )
    return repo_id, snapshot[1], snapshot[2], snapshot[3]


def _list_snapshots(
    data: object, *, resource_type: str, repo_id: int
) -> list[tuple[str, str, str, str]]:
    if not isinstance(data, list):
        raise GitHubTransportError("github_invalid_response")
    result: list[tuple[str, str, str, str]] = []
    seen: set[int] = set()
    for raw in data:
        value = _required_dict(raw)
        if resource_type == "issue" and "pull_request" in value:
            continue
        item_id = _integer(value.get("id"))
        if item_id in seen:
            raise GitHubTransportError("github_invalid_response")
        seen.add(item_id)
        title = _string(value.get("title"))
        body = _string(value.get("body"), optional=True)
        state = _string(value.get("state"))
        if state not in {"open", "closed"}:
            raise GitHubTransportError("github_invalid_response")
        updated_at = _github_timestamp(value.get("updated_at"))
        number = _integer(value.get("number"))
        normalized_body = json.dumps(
            {"body": body, "number": number, "state": state},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        prefix = "issue" if resource_type == "issue" else "pull"
        result.append(
            _validated_snapshot(
                repo_id=repo_id,
                item_id=f"github_{prefix}:{item_id}",
                resource_type=resource_type,
                version=f"{updated_at}:{item_id}",
                title=title,
                body=normalized_body,
            )
        )
    return result


def _persist_page(
    session: Session,
    run: ConnectorSyncRun,
    repository_name: str,
    repo_id: int,
    resource_type: str,
    snapshots: list[tuple[str, str, str, str]],
    observed: set[tuple[str, str]],
) -> None:
    account = _captured_account(session, run)
    if repository_name.casefold() not in {
        v.casefold() for v in account.resource_allowlist
    }:
        raise GitHubTransportError("account_revision_drift")
    if resource_type == "repository":
        prior = repository.latest_repository_snapshot(
            session, run.account_id, repository_name
        )
        expected_identity = f"github_repo:{repo_id}"
        if prior is not None and prior.external_resource_id != expected_identity:
            raise GitHubTransportError("github_identity_mismatch")
    now = datetime.now(UTC)
    created = 0
    unchanged = 0
    for item_id, title, body, version in snapshots:
        observed.add((f"github_repo:{repo_id}", item_id))
        item = ExternalItem(
            account_id=run.account_id,
            provider="github",
            external_account_id=run.external_account_id,
            external_resource_id=f"github_repo:{repo_id}",
            external_item_id=item_id,
            resource_type=resource_type,
            provider_source_version=version,
            title=title,
            body=body,
            content_hash=snapshot_content_hash(title, body),
            application_revision=1,
            project_id=run.project_id,
            created_sync_run_id=run.id,
            last_seen_sync_run_id=run.id,
            first_seen_at=now,
            last_seen_at=now,
        )
        _, was_created = repository.record_item_revision(session, item, seen_at=now)
        created += int(was_created)
        unchanged += int(not was_created)
    current_run = repository.get_sync_run(session, run.id)
    assert current_run is not None
    current_run.items_seen += len(snapshots)
    current_run.items_created += created
    current_run.items_unchanged += unchanged
    session.flush()


def _finish(
    session: Session,
    run_id: uuid.UUID,
    *,
    status: str,
    error: str | None,
    complete: bool,
) -> ConnectorSyncRun:
    run = repository.get_sync_run(session, run_id)
    if run is None:
        raise SyncNotFoundError
    run.status = status
    run.safe_error_code = error
    run.reconciliation_complete = complete
    run.completed_at = datetime.now(UTC)
    session.flush()
    return run


def refresh(
    session: Session,
    run: ConnectorSyncRun,
    store: CredentialStore,
    transport_factory: Callable[[], GitHubTransport],
) -> ConnectorSyncRun:
    deadline = time.monotonic() + SYNC_WALL_CLOCK_SECONDS
    run_id = run.id
    run_account_id = run.account_id
    captured_revision = run.account_revision
    observed: set[tuple[str, str]] = set()

    def ensure_deadline() -> None:
        if time.monotonic() >= deadline:
            raise GitHubTransportError("github_deadline_ceiling")

    secret: bytearray | None = None
    transport: GitHubTransport | None = None
    try:
        account = _captured_account(session, run)
        account_identity = account.external_account_id
        repository_names = tuple(account.resource_allowlist)
        reference = validate_credential_reference(account.credential_reference)
        session.rollback()
        secret = store.read(reference)
        transport = transport_factory()
        ensure_deadline()
        with session.begin():
            current = repository.get_sync_run(session, run_id)
            assert current is not None
            _captured_account(session, current)
            current.status = "running"
            current.started_at = datetime.now(UTC)
        ensure_deadline()
        user = _required_dict(transport.user(secret).value)
        login = _string(user.get("login"))
        if login.casefold() != account_identity.casefold():
            raise GitHubTransportError("github_identity_mismatch")
        accepted = 0
        incomplete = False
        validated_repositories: list[tuple[str, int, str, str, str]] = []
        for repository_name in repository_names:
            ensure_deadline()
            with session.begin():
                current = repository.get_sync_run(session, run_id)
                assert current is not None
                _captured_account(session, current)
            repo_page = transport.repository(secret, repository_name)
            repo_id, full_name, repo_body, repo_version = _repository_snapshot(
                repo_page.value, repository_name
            )
            validated_repositories.append(
                (repository_name, repo_id, full_name, repo_body, repo_version)
            )
        ensure_deadline()
        with session.begin():
            current = repository.get_sync_run(session, run_id)
            assert current is not None
            account_row = _captured_account(session, current)
            # "valid" covers identity, configured repository access/identity,
            # credential usability, and the closed application read policy. It
            # does not assert that GitHub exposed every grant held by the PAT.
            account_row.validation_status = "valid"
            account_row.last_validated_at = datetime.now(UTC)
        for (
            repository_name,
            repo_id,
            full_name,
            repo_body,
            repo_version,
        ) in validated_repositories:
            repo_snapshot = [
                (f"github_repo:{repo_id}", full_name, repo_body, repo_version)
            ]
            ensure_deadline()
            with session.begin():
                _persist_page(
                    session,
                    current,
                    repository_name,
                    repo_id,
                    "repository",
                    repo_snapshot,
                    observed,
                )
            accepted += 1
            for resource_type, fetch in (
                ("issue", transport.issues),
                ("pull_request", transport.pulls),
            ):
                for page_number in range(1, MAX_DATA_PAGES + 1):
                    ensure_deadline()
                    with session.begin():
                        current = repository.get_sync_run(session, run_id)
                        assert current is not None
                        _captured_account(session, current)
                    page: GitHubPage = fetch(secret, repository_name, page_number)
                    ensure_deadline()
                    snapshots = _list_snapshots(
                        page.value, resource_type=resource_type, repo_id=repo_id
                    )
                    if accepted + len(snapshots) > MAX_ACCEPTED_ITEMS:
                        raise GitHubTransportError("github_item_ceiling")
                    with session.begin():
                        _persist_page(
                            session,
                            current,
                            repository_name,
                            repo_id,
                            resource_type,
                            snapshots,
                            observed,
                        )
                    accepted += len(snapshots)
                    if not page.may_have_more:
                        break
                    if page_number == MAX_DATA_PAGES:
                        incomplete = True
        with session.begin():
            current = repository.get_sync_run(session, run_id)
            assert current is not None
            if not incomplete:
                _captured_account(session, current)
                repository.reconcile_latest_items(
                    session, current, observed, reconciled_at=datetime.now(UTC)
                )
            return _finish(
                session,
                run_id,
                status="incomplete" if incomplete else "succeeded",
                error="github_pagination_ceiling" if incomplete else None,
                complete=not incomplete,
            )
    except CredentialStoreError as exc:
        session.rollback()
        with session.begin():
            return _finish(
                session, run_id, status="failed", error=exc.code, complete=False
            )
    except GitHubTransportError as exc:
        session.rollback()
        with session.begin():
            if exc.code in _IDENTITY_FAILURES:
                fence_account = repository.lock_account(session, run_account_id)
                if (
                    fence_account is not None
                    and fence_account.revision == captured_revision
                ):
                    fence_account.lifecycle = "disabled"
                    fence_account.validation_status = "invalid"
                    fence_account.last_validated_at = None
                    fence_account.revision += 1
            return _finish(
                session,
                run_id,
                status="incomplete" if exc.code in _CEILING_CODES else "failed",
                error=exc.code,
                complete=False,
            )
    finally:
        if secret is not None:
            clear_secret(secret)
        close = getattr(transport, "close", None)
        if callable(close):
            close()
