"""Typed loopback-only, PostgreSQL-read-only Context Hub API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.context_hub.models import (
    ContextDetailRequest,
    ContextHubFacets,
    ContextHubPage,
    ContextHubPageRequest,
    ContextHubQuery,
    PublicContextFamilyResult,
    PublicContextItem,
)
from app.context_hub.service import (
    ContextFacetLimitError,
    ContextNotFoundError,
    facet_context,
    query_context_page,
    reopen_context,
)
from app.context_hub.tokens import (
    ContextTokenError,
    decode_cursor,
    decode_reopen,
    encode_cursor,
    encode_reopen,
)
from app.core.config import Settings, get_settings
from app.db.dependencies import get_db_session

router = APIRouter(prefix="/context-hub", tags=["context-hub"])


def _require_loopback(request: Request) -> None:
    host = request.client.host if request.client else None
    if host not in {"127.0.0.1", "::1"}:
        raise HTTPException(403, "context hub forbidden")


def _read_only(session: Session) -> None:
    session.execute(text("SET TRANSACTION READ ONLY"))


def _public(
    item: object, secret: str, reopen_id: str | None = None
) -> PublicContextItem:
    from app.context_hub.models import ContextItem

    assert isinstance(item, ContextItem)
    return PublicContextItem(
        family=item.family,
        kind=item.kind,
        scope=item.scope,
        trust=item.trust,
        state=item.state,
        title=item.title,
        text=item.text,
        reopen_id=reopen_id or encode_reopen(item.scope, item.provenance, secret),
    )


@router.post("/query", response_model=ContextHubPage)
def query_context_hub(
    body: ContextHubPageRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ContextHubPage:
    _require_loopback(request)
    query = ContextHubQuery.model_validate(body.model_dump(exclude={"cursor"}))
    try:
        _read_only(session)
        positions, exhausted = (
            decode_cursor(
                body.cursor, query, settings.postgres_password.get_secret_value()
            )
            if body.cursor is not None
            else ({}, {})
        )
        result, next_positions = query_context_page(
            session, query, positions, exhausted
        )
        next_exhausted = {
            family: next(
                (group.exhausted for group in result.groups if group.family == family),
                True,
            )
            for family in query.families
        }
        for family in query.families:
            next_positions.setdefault(family, positions.get(family))
        next_cursor = (
            None
            if all(next_exhausted.values())
            else encode_cursor(
                query,
                next_positions,
                next_exhausted,
                settings.postgres_password.get_secret_value(),
            )
        )
        return ContextHubPage(
            groups=tuple(
                PublicContextFamilyResult(
                    family=group.family,
                    items=tuple(
                        _public(item, settings.postgres_password.get_secret_value())
                        for item in group.items
                    ),
                    exhausted=group.exhausted,
                )
                for group in result.groups
            ),
            next_cursor=next_cursor,
        )
    except ContextTokenError:
        raise HTTPException(422, "invalid context hub cursor") from None
    except ContextNotFoundError:
        raise HTTPException(404, "context hub scope not found") from None
    except SQLAlchemyError:
        raise HTTPException(503, "database unavailable") from None
    finally:
        session.rollback()


@router.post("/detail", response_model=PublicContextItem)
def detail_context_hub(
    body: ContextDetailRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PublicContextItem:
    _require_loopback(request)
    try:
        _read_only(session)
        secret = settings.postgres_password.get_secret_value()
        provenance = decode_reopen(body.reopen_id, body.scope, body.family, secret)
        return _public(
            reopen_context(session, body.scope, provenance), secret, body.reopen_id
        )
    except (ContextTokenError, ContextNotFoundError):
        raise HTTPException(404, "context hub item not found") from None
    except SQLAlchemyError:
        raise HTTPException(503, "database unavailable") from None
    finally:
        session.rollback()


@router.post("/facets", response_model=ContextHubFacets)
def facets_context_hub(
    body: ContextHubQuery,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> ContextHubFacets:
    _require_loopback(request)
    try:
        _read_only(session)
        return facet_context(session, body)
    except ContextNotFoundError:
        raise HTTPException(404, "context hub scope not found") from None
    except ContextFacetLimitError:
        raise HTTPException(422, "context hub facet limit exceeded") from None
    except SQLAlchemyError:
        raise HTTPException(503, "database unavailable") from None
    finally:
        session.rollback()
