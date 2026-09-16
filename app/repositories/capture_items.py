"""Caller-transaction-owned Capture persistence primitives."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import REAL, Select, and_, cast, func, literal, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models.capture_item import CaptureItem


def insert_capture_on_new_key(
    session: Session, item: CaptureItem
) -> CaptureItem | None:
    """Atomically claim a key and return the inserted ORM row, if any."""

    values = {
        column.name: getattr(item, column.name)
        for column in CaptureItem.__table__.columns
        if column.name != "search_vector"
    }
    statement = (
        insert(CaptureItem)
        .values(**values)
        .on_conflict_do_nothing(index_elements=["idempotency_key_hash"])
        .returning(CaptureItem)
    )
    return session.scalars(statement).one_or_none()


def get_capture_by_idempotency_hash(
    session: Session, idempotency_key_hash: str
) -> CaptureItem | None:
    return session.scalar(
        select(CaptureItem).where(
            CaptureItem.idempotency_key_hash == idempotency_key_hash
        )
    )


def _scope_predicate(project_id: uuid.UUID | None) -> ColumnElement[bool]:
    return (
        CaptureItem.project_id.is_(None)
        if project_id is None
        else CaptureItem.project_id == project_id
    )


def get_scoped_capture(
    session: Session,
    item_id: uuid.UUID,
    project_id: uuid.UUID | None,
    *,
    lock: bool = False,
) -> CaptureItem | None:
    statement = select(CaptureItem).where(
        CaptureItem.id == item_id, _scope_predicate(project_id)
    )
    if lock:
        statement = statement.with_for_update()
    return session.scalar(statement)


def query_captures(
    session: Session,
    *,
    project_id: uuid.UUID | None,
    states: list[str],
    query: str | None,
    page_size: int,
    position: tuple[datetime, uuid.UUID, float | None] | None,
) -> list[tuple[CaptureItem, float | None]]:
    rank = None
    statement: Select[Any]
    if query is None:
        statement = select(CaptureItem, literal(None)).where(
            _scope_predicate(project_id), CaptureItem.state.in_(states)
        )
        if position is not None:
            created_at, item_id, _ = position
            statement = statement.where(
                or_(
                    CaptureItem.created_at < created_at,
                    and_(
                        CaptureItem.created_at == created_at, CaptureItem.id < item_id
                    ),
                )
            )
        statement = statement.order_by(
            CaptureItem.created_at.desc(), CaptureItem.id.desc()
        )
    else:
        tsquery = func.plainto_tsquery("simple", query)
        rank = func.ts_rank_cd(CaptureItem.search_vector, tsquery)
        statement = select(CaptureItem, rank).where(
            _scope_predicate(project_id),
            CaptureItem.state.in_(states),
            CaptureItem.search_vector.op("@@")(tsquery),
        )
        if position is not None:
            created_at, item_id, cursor_rank = position
            assert cursor_rank is not None
            bound_rank = cast(cursor_rank, REAL)
            statement = statement.where(
                or_(
                    rank < bound_rank,
                    and_(
                        rank == bound_rank,
                        or_(
                            CaptureItem.created_at < created_at,
                            and_(
                                CaptureItem.created_at == created_at,
                                CaptureItem.id < item_id,
                            ),
                        ),
                    ),
                )
            )
        statement = statement.order_by(
            rank.desc(), CaptureItem.created_at.desc(), CaptureItem.id.desc()
        )
    return [
        (row[0], None if query is None else float(row[1]))
        for row in session.execute(statement.limit(page_size + 1)).all()
    ]
