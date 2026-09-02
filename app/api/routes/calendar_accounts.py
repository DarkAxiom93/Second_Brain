"""Loopback-only safe Calendar account metadata routes."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.calendar import service
from app.calendar.dependencies import (
    CalendarCredentialBoundary,
    calendar_credential_dependency,
)
from app.credentials import CredentialStoreError, validate_credential_reference
from app.db.dependencies import get_db_session
from app.google_oauth.contract import GoogleOAuthError
from app.models.calendar import CalendarAccountRevision
from app.schemas.calendar import (
    CalendarAccountCreate,
    CalendarAccountRead,
    CalendarAccountUpdate,
    CalendarRevisionRequest,
    CalendarRevocationRead,
)

router = APIRouter(prefix="/calendar-accounts", tags=["calendar-accounts"])


def _error(code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


def _mutation(
    session: Session,
    boundary: CalendarCredentialBoundary,
    operation: Callable[[], CalendarAccountRevision],
) -> CalendarAccountRead:
    try:
        account = operation()
        session.commit()
        session.refresh(account)
        return service.public_account(
            account, service.safe_credential_status(account, boundary)
        )
    except service.CalendarNotFoundError:
        session.rollback()
        raise _error(404, "calendar account not found") from None
    except service.CalendarProjectNotFoundError:
        session.rollback()
        raise _error(404, "project not found") from None
    except service.CalendarRevisionConflictError:
        session.rollback()
        raise _error(409, "calendar account revision conflict") from None
    except service.CalendarTransitionConflictError:
        session.rollback()
        raise _error(409, "calendar account transition conflict") from None
    except service.CalendarCredentialError:
        session.rollback()
        raise _error(409, "calendar credential unavailable") from None
    except service.CalendarDefinitionError:
        session.rollback()
        raise _error(422, "invalid calendar account configuration") from None
    except IntegrityError:
        session.rollback()
        raise _error(409, "calendar account conflict") from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(503, "database unavailable") from None


@router.post(
    "", response_model=CalendarAccountRead, status_code=status.HTTP_201_CREATED
)
def create_account(
    request: CalendarAccountCreate,
    session: Annotated[Session, Depends(get_db_session)],
    boundary: Annotated[
        CalendarCredentialBoundary, Depends(calendar_credential_dependency)
    ],
) -> CalendarAccountRead:
    return _mutation(
        session, boundary, lambda: service.create_account(session, request, boundary)
    )


@router.get("", response_model=list[CalendarAccountRead])
def list_accounts(
    session: Annotated[Session, Depends(get_db_session)],
    boundary: Annotated[
        CalendarCredentialBoundary, Depends(calendar_credential_dependency)
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CalendarAccountRead]:
    try:
        return [
            service.public_account(
                account, service.safe_credential_status(account, boundary)
            )
            for account in service.list_accounts(session, limit=limit, offset=offset)
        ]
    except SQLAlchemyError:
        raise _error(503, "database unavailable") from None


@router.get("/{account_id}", response_model=CalendarAccountRead)
def get_account(
    account_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
    boundary: Annotated[
        CalendarCredentialBoundary, Depends(calendar_credential_dependency)
    ],
) -> CalendarAccountRead:
    try:
        account = service.get_account(session, account_id)
    except service.CalendarNotFoundError:
        raise _error(404, "calendar account not found") from None
    except SQLAlchemyError:
        raise _error(503, "database unavailable") from None
    return service.public_account(
        account, service.safe_credential_status(account, boundary)
    )


@router.patch("/{account_id}", response_model=CalendarAccountRead)
def update_account(
    account_id: uuid.UUID,
    request: CalendarAccountUpdate,
    session: Annotated[Session, Depends(get_db_session)],
    boundary: Annotated[
        CalendarCredentialBoundary, Depends(calendar_credential_dependency)
    ],
) -> CalendarAccountRead:
    return _mutation(
        session,
        boundary,
        lambda: service.update_account(session, account_id, request, boundary),
    )


def _lifecycle(
    account_id: uuid.UUID,
    request: CalendarRevisionRequest,
    session: Session,
    boundary: CalendarCredentialBoundary,
    target: str,
) -> CalendarAccountRead:
    return _mutation(
        session,
        boundary,
        lambda: service.set_lifecycle(
            session, account_id, request.expected_revision, target, boundary
        ),
    )


@router.post("/{account_id}/disable", response_model=CalendarAccountRead)
def disable(
    account_id: uuid.UUID,
    request: CalendarRevisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
    boundary: Annotated[
        CalendarCredentialBoundary, Depends(calendar_credential_dependency)
    ],
) -> CalendarAccountRead:
    return _lifecycle(account_id, request, session, boundary, "disabled")


@router.post("/{account_id}/re-enable", response_model=CalendarAccountRead)
def re_enable(
    account_id: uuid.UUID,
    request: CalendarRevisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
    boundary: Annotated[
        CalendarCredentialBoundary, Depends(calendar_credential_dependency)
    ],
) -> CalendarAccountRead:
    return _lifecycle(account_id, request, session, boundary, "enabled")


@router.post("/{account_id}/revoke", response_model=CalendarRevocationRead)
def revoke(
    account_id: uuid.UUID,
    request: CalendarRevisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
    boundary: Annotated[
        CalendarCredentialBoundary, Depends(calendar_credential_dependency)
    ],
) -> CalendarRevocationRead:
    try:
        revoked = service.revoke(session, account_id, request.expected_revision)
        reference = validate_credential_reference(revoked.credential_reference)
        session.commit()
        session.refresh(revoked)
    except service.CalendarNotFoundError:
        session.rollback()
        raise _error(404, "calendar account not found") from None
    except service.CalendarRevisionConflictError:
        session.rollback()
        raise _error(409, "calendar account revision conflict") from None
    except service.CalendarTransitionConflictError:
        session.rollback()
        raise _error(409, "calendar account transition conflict") from None
    except (IntegrityError, SQLAlchemyError):
        session.rollback()
        raise _error(503, "calendar account operation unavailable") from None
    try:
        result = boundary.revoke(reference)
    except (CredentialStoreError, GoogleOAuthError, ValueError):
        result = None
    return CalendarRevocationRead(
        account=service.public_account(revoked, "revoked"),
        provider_revoked=False if result is None else result.provider_revoked,
        local_deleted=False if result is None else result.local_deleted,
    )
