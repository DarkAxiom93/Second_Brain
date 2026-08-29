"""Short-transaction, revision-aware connector account lifecycle service.

Configuration is mutable only while disabled. Historical sync runs and external
items retain their captured Project/resource scope; this service never remaps them.
"""

import uuid
from hashlib import sha256
from typing import cast

from sqlalchemy.orm import Session

from app.connectors.validation import granted_scope_fingerprint, validate_account_values
from app.models.connector import ConnectorAccount
from app.models.project import Project
from app.repositories import connectors as repository
from app.schemas.connector import (
    ConnectorAccountCreate,
    ConnectorAccountRead,
    ConnectorAccountUpdate,
    ConnectorScope,
    Lifecycle,
    ValidationStatus,
)

_PROVIDER = "github"
_APPLICATION_READ_POLICY = (
    "metadata_read",
    "issues_read",
    "pull_requests_read",
)


class ConnectorNotFoundError(Exception):
    pass


class ConnectorRevisionConflictError(Exception):
    pass


class ConnectorTransitionConflictError(Exception):
    pass


class ConnectorProjectNotFoundError(Exception):
    pass


class ConnectorConfigurationConflictError(Exception):
    pass


class ConnectorDefinitionError(ValueError):
    pass


def _project_id(session: Session, scope: ConnectorScope) -> uuid.UUID | None:
    if scope.kind == "unassigned":
        return None
    assert scope.project_id is not None
    if session.get(Project, scope.project_id) is None:
        raise ConnectorProjectNotFoundError
    return scope.project_id


def _repositories(values: list[str]) -> list[str]:
    result = sorted(values, key=str.casefold)
    if len({value.casefold() for value in result}) != len(result):
        raise ConnectorDefinitionError("invalid repository allowlist")
    # Reuse the persistence boundary's closed canonical owner/repository validator.
    validate_account_values(
        provider=_PROVIDER,
        external_account_id="validation",
        external_account_fingerprint="0" * 64,
        credential_reference="sbcred:v1:00000000-0000-4000-8000-000000000000",
        resource_allowlist=result,
        granted_scope_fingerprint="0" * 64,
    )
    return result


def _external_fingerprint(identity: str) -> str:
    return sha256(f"{_PROVIDER}\n{identity}".encode()).hexdigest()


def _lock_expected(
    session: Session, account_id: uuid.UUID, expected_revision: int
) -> ConnectorAccount:
    account = repository.lock_account(session, account_id)
    if account is None:
        raise ConnectorNotFoundError
    if account.revision != expected_revision:
        raise ConnectorRevisionConflictError
    return account


def create_account(
    session: Session, request: ConnectorAccountCreate
) -> ConnectorAccount:
    repositories = _repositories(request.repositories)
    account = ConnectorAccount(
        provider=_PROVIDER,
        external_account_id=request.external_account_identity,
        external_account_fingerprint=_external_fingerprint(
            request.external_account_identity
        ),
        credential_reference=request.credential_reference,
        project_id=_project_id(session, request.scope),
        resource_allowlist=repositories,
        granted_scope_fingerprint=granted_scope_fingerprint(_APPLICATION_READ_POLICY),
        lifecycle="disabled",
        validation_status="unvalidated",
        revision=0,
    )
    return repository.create_account(session, account)


def update_account(
    session: Session, account_id: uuid.UUID, request: ConnectorAccountUpdate
) -> ConnectorAccount:
    account = _lock_expected(session, account_id, request.expected_revision)
    if account.lifecycle != "disabled" or repository.has_active_sync_run(
        session, account.id
    ):
        raise ConnectorConfigurationConflictError
    if request.scope is not None:
        account.project_id = _project_id(session, request.scope)
    if request.repositories is not None:
        account.resource_allowlist = _repositories(request.repositories)
    account.validation_status = "unvalidated"
    account.last_validated_at = None
    account.revision += 1
    session.flush()
    session.refresh(account)
    return account


def set_lifecycle(
    session: Session, account_id: uuid.UUID, expected_revision: int, target: str
) -> ConnectorAccount:
    account = _lock_expected(session, account_id, expected_revision)
    allowed = {
        ("enabled", "disabled"),
        ("disabled", "enabled"),
        ("disabled", "revoked"),
        ("enabled", "revoked"),
    }
    if (account.lifecycle, target) not in allowed:
        raise ConnectorTransitionConflictError
    account.lifecycle = target
    if target == "revoked":
        account.validation_status = "revoked"
        account.last_validated_at = None
    account.revision += 1
    session.flush()
    session.refresh(account)
    return account


def public_account(account: ConnectorAccount) -> ConnectorAccountRead:
    return ConnectorAccountRead(
        id=account.id,
        provider="github",
        external_account_identity=account.external_account_id,
        scope=ConnectorScope(
            kind="project" if account.project_id else "unassigned",
            project_id=account.project_id,
        ),
        repositories=list(account.resource_allowlist),
        lifecycle=cast(Lifecycle, account.lifecycle),
        validation_status=cast(ValidationStatus, account.validation_status),
        revision=account.revision,
        last_validated_at=account.last_validated_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )
