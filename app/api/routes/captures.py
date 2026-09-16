"""Loopback Capture Inbox API with exact-scope reads and mutations."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.captures import service
from app.captures.tokens import CaptureCursorError, decode_cursor, encode_cursor
from app.core.config import Settings, get_settings
from app.db.dependencies import get_db_session
from app.schemas.capture import (
    CaptureCreateRequest,
    CaptureDetailRequest,
    CaptureEditRequest,
    CapturePage,
    CaptureQueryRequest,
    CaptureRead,
    CaptureReassignRequest,
    CaptureRevisionRequest,
)

router = APIRouter(prefix="/capture-items", tags=["capture-items"])


def _loopback(request: Request) -> None:
    if (request.client.host if request.client else None) not in {"127.0.0.1", "::1"}:
        raise HTTPException(403, "capture inbox forbidden")


def _error(code: int, detail: object) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


def _conflict(exc: service.CaptureRevisionConflictError) -> HTTPException:
    return _error(
        409,
        {
            "error": "capture revision conflict",
            "item": CaptureRead.model_validate(exc.item).model_dump(mode="json"),
        },
    )


def _mutation(
    session: Session, operation: Callable[[], service.CaptureItemProjection]
) -> CaptureRead:
    try:
        item = operation()
        session.commit()
        return CaptureRead.model_validate(item)
    except service.CaptureNotFoundError:
        session.rollback()
        raise _error(404, "capture item not found") from None
    except service.CaptureProjectNotFoundError:
        session.rollback()
        raise _error(404, "project not found") from None
    except service.CaptureRevisionConflictError as exc:
        session.rollback()
        raise _conflict(exc) from None
    except service.CaptureTransitionConflictError:
        session.rollback()
        raise _error(409, "capture transition conflict") from None
    except service.CaptureValidationError as exc:
        session.rollback()
        raise _error(422, str(exc)) from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(503, "database unavailable") from None


@router.post("", response_model=CaptureRead, status_code=201)
def create_capture(
    body: CaptureCreateRequest,
    response: Response,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> CaptureRead:
    _loopback(request)
    try:
        result = service.create_capture(
            session,
            service.CaptureCreate(
                content=body.content,
                idempotency_key=idempotency_key,
                project_id=body.project_id,
            ),
        )
        session.commit()
        response.status_code = 201 if result.created else 200
        return CaptureRead.model_validate(result.item)
    except service.CaptureProjectNotFoundError:
        session.rollback()
        raise _error(404, "project not found") from None
    except service.CaptureIdempotencyConflictError:
        session.rollback()
        raise _error(409, "capture idempotency conflict") from None
    except service.CaptureValidationError as exc:
        session.rollback()
        raise _error(422, str(exc)) from None
    except SQLAlchemyError:
        session.rollback()
        raise _error(503, "database unavailable") from None


@router.post("/query", response_model=CapturePage)
def query_captures(
    body: CaptureQueryRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CapturePage:
    _loopback(request)
    try:
        secret = settings.postgres_password.get_secret_value()
        raw_position = decode_cursor(body.cursor, body, secret) if body.cursor else None
        position = (
            None
            if raw_position is None
            else (raw_position[0], uuid.UUID(raw_position[1]), raw_position[2])
        )
        rows = service.query_capture_items(session, body, position)
        has_more = len(rows) > body.page_size
        rows = rows[: body.page_size]
        next_cursor = None
        if has_more:
            item, rank = rows[-1]
            next_cursor = encode_cursor(
                body, item.created_at, str(item.id), rank, secret
            )
        return CapturePage(
            items=[CaptureRead.model_validate(item) for item, _ in rows],
            next_cursor=next_cursor,
        )
    except CaptureCursorError:
        raise _error(422, "invalid capture cursor") from None
    except service.CaptureProjectNotFoundError:
        raise _error(404, "project not found") from None
    except SQLAlchemyError:
        raise _error(503, "database unavailable") from None
    finally:
        session.rollback()


@router.post("/{item_id}/detail", response_model=CaptureRead)
def detail_capture(
    item_id: uuid.UUID,
    body: CaptureDetailRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> CaptureRead:
    _loopback(request)
    try:
        return CaptureRead.model_validate(
            service.detail_capture(session, item_id, body.scope)
        )
    except service.CaptureProjectNotFoundError:
        raise _error(404, "project not found") from None
    except service.CaptureNotFoundError:
        raise _error(404, "capture item not found") from None
    except SQLAlchemyError:
        raise _error(503, "database unavailable") from None
    finally:
        session.rollback()


@router.patch("/{item_id}", response_model=CaptureRead)
def edit_capture(
    item_id: uuid.UUID,
    body: CaptureEditRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> CaptureRead:
    _loopback(request)
    return _mutation(
        session,
        lambda: service.edit_capture(
            session, item_id, body.scope, body.revision, body.content
        ),
    )


@router.post("/{item_id}/reassign", response_model=CaptureRead)
def reassign_capture(
    item_id: uuid.UUID,
    body: CaptureReassignRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> CaptureRead:
    _loopback(request)
    return _mutation(
        session,
        lambda: service.reassign_capture(
            session, item_id, body.scope, body.target_scope, body.revision
        ),
    )


def _transition(
    item_id: uuid.UUID,
    body: CaptureRevisionRequest,
    request: Request,
    session: Session,
    expected: str,
    target: str,
) -> CaptureRead:
    _loopback(request)
    return _mutation(
        session,
        lambda: service.transition_capture(
            session,
            item_id,
            body.scope,
            body.revision,
            expected=expected,
            target=target,
        ),
    )


@router.post("/{item_id}/discard", response_model=CaptureRead)
def discard_capture(
    item_id: uuid.UUID,
    body: CaptureRevisionRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> CaptureRead:
    return _transition(item_id, body, request, session, "pending", "discarded")


@router.post("/{item_id}/restore", response_model=CaptureRead)
def restore_capture(
    item_id: uuid.UUID,
    body: CaptureRevisionRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> CaptureRead:
    return _transition(item_id, body, request, session, "discarded", "pending")
