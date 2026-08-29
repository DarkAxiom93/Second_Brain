"""Loopback-only, metadata-only connector account routes."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.connectors import service
from app.connectors import sync as sync_service
from app.connectors.dependencies import (
    credential_store_dependency,
    github_transport_factory_dependency,
)
from app.connectors.github import GitHubTransport
from app.credentials.contract import CredentialStore
from app.db.dependencies import get_db_session
from app.models.connector import ConnectorAccount
from app.repositories import connectors as repository
from app.schemas.connector import (
    ConnectorAccountCreate,
    ConnectorAccountRead,
    ConnectorAccountUpdate,
    ConnectorRevisionRequest,
    ConnectorSyncRunRead,
)

router = APIRouter(prefix="/connector-accounts", tags=["connector-accounts"])


def _error(code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


def _mutation(
    session: Session, operation: Callable[[], ConnectorAccount]
) -> ConnectorAccountRead:
    try:
        account = operation()
        session.commit()
        session.refresh(account)
        return service.public_account(account)
    except service.ConnectorNotFoundError:
        session.rollback()
        raise _error(404, "connector account not found") from None
    except service.ConnectorProjectNotFoundError:
        session.rollback()
        raise _error(404, "project not found") from None
    except service.ConnectorRevisionConflictError:
        session.rollback()
        raise _error(409, "connector account revision conflict") from None
    except service.ConnectorTransitionConflictError:
        session.rollback()
        raise _error(409, "connector account transition conflict") from None
    except service.ConnectorConfigurationConflictError:
        session.rollback()
        raise _error(409, "connector account configuration conflict") from None
    except (service.ConnectorDefinitionError, ValueError):
        session.rollback()
        raise _error(422, "invalid connector account configuration") from None
    except IntegrityError:
        session.rollback()
        raise _error(409, "connector account conflict") from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(503, "database unavailable") from None


@router.post(
    "", response_model=ConnectorAccountRead, status_code=status.HTTP_201_CREATED
)
def create_account(
    request: ConnectorAccountCreate,
    session: Annotated[Session, Depends(get_db_session)],
) -> ConnectorAccountRead:
    return _mutation(session, lambda: service.create_account(session, request))


@router.get("", response_model=list[ConnectorAccountRead])
def list_accounts(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ConnectorAccountRead]:
    try:
        return [
            service.public_account(value)
            for value in repository.list_accounts(session, limit=limit, offset=offset)
        ]
    except SQLAlchemyError:
        raise _error(503, "database unavailable") from None


@router.get("/{account_id}", response_model=ConnectorAccountRead)
def get_account(
    account_id: uuid.UUID, session: Annotated[Session, Depends(get_db_session)]
) -> ConnectorAccountRead:
    try:
        account = repository.get_account(session, account_id)
    except SQLAlchemyError:
        raise _error(503, "database unavailable") from None
    if account is None:
        raise _error(404, "connector account not found")
    return service.public_account(account)


@router.patch("/{account_id}", response_model=ConnectorAccountRead)
def update_account(
    account_id: uuid.UUID,
    request: ConnectorAccountUpdate,
    session: Annotated[Session, Depends(get_db_session)],
) -> ConnectorAccountRead:
    return _mutation(
        session, lambda: service.update_account(session, account_id, request)
    )


def _lifecycle(
    account_id: uuid.UUID,
    request: ConnectorRevisionRequest,
    session: Session,
    target: str,
) -> ConnectorAccountRead:
    return _mutation(
        session,
        lambda: service.set_lifecycle(
            session, account_id, request.expected_revision, target
        ),
    )


@router.post("/{account_id}/disable", response_model=ConnectorAccountRead)
def disable(
    account_id: uuid.UUID,
    request: ConnectorRevisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ConnectorAccountRead:
    return _lifecycle(account_id, request, session, "disabled")


@router.post("/{account_id}/re-enable", response_model=ConnectorAccountRead)
def re_enable(
    account_id: uuid.UUID,
    request: ConnectorRevisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ConnectorAccountRead:
    return _lifecycle(account_id, request, session, "enabled")


@router.post("/{account_id}/revoke", response_model=ConnectorAccountRead)
def revoke(
    account_id: uuid.UUID,
    request: ConnectorRevisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ConnectorAccountRead:
    return _lifecycle(account_id, request, session, "revoked")


@router.post("/{account_id}/refresh", response_model=ConnectorSyncRunRead)
def refresh(
    account_id: uuid.UUID,
    request: ConnectorRevisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
    store: Annotated[CredentialStore, Depends(credential_store_dependency)],
    transport_factory: Annotated[
        Callable[[], GitHubTransport], Depends(github_transport_factory_dependency)
    ],
) -> ConnectorSyncRunRead:
    try:
        run = sync_service.claim(session, account_id, request.expected_revision)
        session.commit()
        session.refresh(run)
    except sync_service.SyncNotFoundError:
        session.rollback()
        raise _error(404, "connector account not found") from None
    except sync_service.SyncRevisionConflictError:
        session.rollback()
        raise _error(409, "connector account revision conflict") from None
    except (sync_service.SyncConflictError, sync_service.SyncCapacityConflictError):
        session.rollback()
        raise _error(409, "connector refresh conflict") from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(503, "database unavailable") from None
    result = sync_service.refresh(session, run, store, transport_factory)
    session.commit()
    session.refresh(result)
    return sync_service.public_sync_run(result)


@router.get("/{account_id}/sync-status", response_model=ConnectorSyncRunRead | None)
def latest_sync_status(
    account_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> ConnectorSyncRunRead | None:
    try:
        if repository.get_account(session, account_id) is None:
            raise _error(404, "connector account not found")
        run = repository.latest_sync_run(session, account_id)
        return None if run is None else sync_service.public_sync_run(run)
    except SQLAlchemyError:
        raise _error(503, "database unavailable") from None
