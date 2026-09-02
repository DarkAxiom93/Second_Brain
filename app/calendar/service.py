"""Revision-fenced, metadata-only Calendar account lifecycle."""

import uuid
from typing import Literal, cast

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.calendar.dependencies import CalendarCredentialBoundary
from app.credentials import CredentialStoreError, validate_credential_reference
from app.google_oauth.contract import GoogleOAuthError
from app.models.calendar import CalendarAccountRevision, CalendarIdentity
from app.models.project import Project
from app.schemas.calendar import (
    CalendarAccountCreate,
    CalendarAccountRead,
    CalendarAccountUpdate,
    CalendarScope,
)


class CalendarNotFoundError(Exception):
    pass


class CalendarRevisionConflictError(Exception):
    pass


class CalendarTransitionConflictError(Exception):
    pass


class CalendarProjectNotFoundError(Exception):
    pass


class CalendarCredentialError(Exception):
    pass


class CalendarDefinitionError(Exception):
    pass


def _project_id(session: Session, scope: CalendarScope) -> uuid.UUID | None:
    if scope.kind == "unassigned":
        return None
    assert scope.project_id is not None
    if session.get(Project, scope.project_id) is None:
        raise CalendarProjectNotFoundError
    return scope.project_id


def _calendar_ids(values: list[str]) -> list[str]:
    if not 1 <= len(values) <= 10:
        raise CalendarDefinitionError
    if any(
        not value.strip() or value != value.strip() or len(value.encode()) > 4096
        for value in values
    ):
        raise CalendarDefinitionError
    if len(set(values)) != len(values):
        raise CalendarDefinitionError
    return sorted(values)


def _credential(
    boundary: CalendarCredentialBoundary,
    reference_value: str,
    expected_fingerprint: str,
) -> str:
    try:
        reference = validate_credential_reference(reference_value)
        status = boundary.status(reference)
        if set(status) != {
            "status",
            "credential_reference",
            "account_fingerprint",
            "generation",
        }:
            raise CalendarCredentialError
        if (
            status["status"] != "authorized"
            or status["credential_reference"] != reference_value
        ):
            raise CalendarCredentialError
        if status["account_fingerprint"] != expected_fingerprint:
            raise CalendarCredentialError
        if not isinstance(status["generation"], int) or status["generation"] < 1:
            raise CalendarCredentialError
        return reference_value
    except (
        CredentialStoreError,
        GoogleOAuthError,
        ValueError,
        CalendarCredentialError,
    ):
        raise CalendarCredentialError from None


def _latest_query() -> Select[tuple[CalendarAccountRevision]]:
    latest = (
        select(
            CalendarAccountRevision.configuration_id,
            func.max(CalendarAccountRevision.configuration_revision).label("revision"),
        )
        .group_by(CalendarAccountRevision.configuration_id)
        .subquery()
    )
    return (
        select(CalendarAccountRevision)
        .join(
            latest,
            (CalendarAccountRevision.configuration_id == latest.c.configuration_id)
            & (CalendarAccountRevision.configuration_revision == latest.c.revision),
        )
        .options(selectinload(CalendarAccountRevision.calendars))
    )


def get_account(
    session: Session, account_id: uuid.UUID, *, lock: bool = False
) -> CalendarAccountRevision:
    query = _latest_query().where(
        CalendarAccountRevision.configuration_id == account_id
    )
    if lock:
        query = query.with_for_update(of=CalendarAccountRevision)
    account = session.scalar(query)
    if account is None:
        raise CalendarNotFoundError
    return account


def list_accounts(
    session: Session, *, limit: int, offset: int
) -> list[CalendarAccountRevision]:
    return list(
        session.scalars(
            _latest_query()
            .order_by(
                CalendarAccountRevision.created_at.desc(),
                CalendarAccountRevision.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).unique()
    )


def _ensure_unique(
    session: Session,
    calendar_ids: list[str],
    account_id: uuid.UUID | None = None,
) -> None:
    for account in list_accounts(session, limit=100, offset=0):
        if account_id is not None and account.configuration_id == account_id:
            continue
        existing = {item.provider_calendar_id for item in account.calendars}
        if existing.intersection(calendar_ids):
            raise CalendarDefinitionError


def _append(
    session: Session,
    *,
    previous: CalendarAccountRevision | None,
    fingerprint: str,
    reference: str,
    project_id: uuid.UUID | None,
    lifecycle: str,
    calendar_ids: list[str],
) -> CalendarAccountRevision:
    account = CalendarAccountRevision(
        configuration_id=uuid.uuid4()
        if previous is None
        else previous.configuration_id,
        configuration_revision=1
        if previous is None
        else previous.configuration_revision + 1,
        account_fingerprint=fingerprint,
        credential_reference=reference,
        project_id=project_id,
        lifecycle=lifecycle,
        configuration_state="configured"
        if lifecycle != "revoked"
        else "reauthorization_required",
    )
    session.add(account)
    session.flush()
    for value in calendar_ids:
        session.add(
            CalendarIdentity(
                account_revision_id=account.id,
                account_fingerprint=fingerprint,
                provider_calendar_id=value,
            )
        )
    session.flush()
    session.refresh(account)
    return account


def create_account(
    session: Session,
    request: CalendarAccountCreate,
    boundary: CalendarCredentialBoundary,
) -> CalendarAccountRevision:
    ids = _calendar_ids(request.calendar_ids)
    reference = _credential(
        boundary, request.credential_reference, request.account_fingerprint
    )
    _ensure_unique(session, ids)
    return _append(
        session,
        previous=None,
        fingerprint=request.account_fingerprint,
        reference=reference,
        project_id=_project_id(session, request.scope),
        lifecycle="enabled",
        calendar_ids=ids,
    )


def update_account(
    session: Session,
    account_id: uuid.UUID,
    request: CalendarAccountUpdate,
    boundary: CalendarCredentialBoundary,
) -> CalendarAccountRevision:
    previous = get_account(session, account_id, lock=True)
    if previous.configuration_revision != request.expected_revision:
        raise CalendarRevisionConflictError
    if previous.lifecycle != "disabled":
        raise CalendarTransitionConflictError
    ids = _calendar_ids(
        request.calendar_ids or [x.provider_calendar_id for x in previous.calendars]
    )
    reference = request.credential_reference or previous.credential_reference
    _credential(boundary, reference, previous.account_fingerprint)
    _ensure_unique(session, ids, account_id)
    project_id = (
        previous.project_id
        if request.scope is None
        else _project_id(session, request.scope)
    )
    return _append(
        session,
        previous=previous,
        fingerprint=previous.account_fingerprint,
        reference=reference,
        project_id=project_id,
        lifecycle="disabled",
        calendar_ids=ids,
    )


def set_lifecycle(
    session: Session,
    account_id: uuid.UUID,
    expected_revision: int,
    target: str,
    boundary: CalendarCredentialBoundary,
) -> CalendarAccountRevision:
    previous = get_account(session, account_id, lock=True)
    if previous.configuration_revision != expected_revision:
        raise CalendarRevisionConflictError
    if (previous.lifecycle, target) not in {
        ("enabled", "disabled"),
        ("disabled", "enabled"),
    }:
        raise CalendarTransitionConflictError
    if target == "enabled":
        _credential(
            boundary, previous.credential_reference, previous.account_fingerprint
        )
    return _append(
        session,
        previous=previous,
        fingerprint=previous.account_fingerprint,
        reference=previous.credential_reference,
        project_id=previous.project_id,
        lifecycle=target,
        calendar_ids=[x.provider_calendar_id for x in previous.calendars],
    )


def revoke(
    session: Session, account_id: uuid.UUID, expected_revision: int
) -> CalendarAccountRevision:
    previous = get_account(session, account_id, lock=True)
    if previous.configuration_revision != expected_revision:
        raise CalendarRevisionConflictError
    if previous.lifecycle == "revoked":
        raise CalendarTransitionConflictError
    account = _append(
        session,
        previous=previous,
        fingerprint=previous.account_fingerprint,
        reference=previous.credential_reference,
        project_id=previous.project_id,
        lifecycle="revoked",
        calendar_ids=[x.provider_calendar_id for x in previous.calendars],
    )
    return account


def public_account(
    account: CalendarAccountRevision, credential_status: str
) -> CalendarAccountRead:
    return CalendarAccountRead(
        id=account.configuration_id,
        account_fingerprint=account.account_fingerprint,
        lifecycle=cast(Literal["enabled", "disabled", "revoked"], account.lifecycle),
        configuration_revision=account.configuration_revision,
        scope=CalendarScope(
            kind="project" if account.project_id else "unassigned",
            project_id=account.project_id,
        ),
        calendar_ids=sorted(x.provider_calendar_id for x in account.calendars),
        credential_status=cast(
            Literal["valid", "missing", "unavailable", "revoked"], credential_status
        ),
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


def safe_credential_status(
    account: CalendarAccountRevision, boundary: CalendarCredentialBoundary
) -> str:
    if account.lifecycle == "revoked":
        return "revoked"
    try:
        _credential(boundary, account.credential_reference, account.account_fingerprint)
        return "valid"
    except CalendarCredentialError:
        return "missing"
