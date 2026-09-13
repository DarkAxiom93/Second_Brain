"""Caller-transaction-owned Capture persistence primitives."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

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
