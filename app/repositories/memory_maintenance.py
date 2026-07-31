"""Read-only SQL queries for Memory maintenance conditions."""

import uuid
from datetime import datetime

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.memory_embedding import MemoryEmbedding
from app.repositories.memory_embedding_batches import stale_embedding_predicate


def aggregate_counts(session: Session) -> tuple[int, int, dict[str, int]]:
    """Return total, assigned, and status counts without loading model rows."""

    rows = session.execute(
        select(
            Memory.status,
            func.count(Memory.id),
            func.sum(case((Memory.project_id.is_not(None), 1), else_=0)),
        ).group_by(Memory.status)
    ).all()
    total = sum(int(row[1]) for row in rows)
    assigned = sum(int(row[2] or 0) for row in rows)
    return total, assigned, {str(row[0]): int(row[1]) for row in rows}


def _category(
    session: Session, statement: Select[tuple[uuid.UUID]], limit: int
) -> tuple[int, list[uuid.UUID]]:
    count = int(
        session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    )
    ids = list(session.scalars(statement.limit(limit))) if limit else []
    return count, ids


def category_counts_and_ids(
    session: Session,
    *,
    captured_at: datetime,
    detail_limit: int,
    provider: str,
    model: str,
    dimensions: int,
) -> dict[str, tuple[int, list[uuid.UUID]]]:
    """Return full counts and bounded IDs in stable creation/UUID order."""

    ordered = select(Memory.id).order_by(Memory.created_at, Memory.id)
    with_embedding = ordered.join(MemoryEmbedding)
    return {
        "active_missing_embedding": _category(
            session,
            ordered.outerjoin(MemoryEmbedding).where(
                Memory.status == "active", MemoryEmbedding.id.is_(None)
            ),
            detail_limit,
        ),
        "active_stale_embedding": _category(
            session,
            with_embedding.where(
                Memory.status == "active",
                stale_embedding_predicate(
                    provider=provider, model=model, dimensions=dimensions
                ),
            ),
            detail_limit,
        ),
        "active_expiration_due": _category(
            session,
            ordered.where(
                Memory.status == "active",
                Memory.expires_at.is_not(None),
                Memory.expires_at <= captured_at,
            ),
            detail_limit,
        ),
        "active_future_expiration": _category(
            session,
            ordered.where(Memory.status == "active", Memory.expires_at > captured_at),
            detail_limit,
        ),
        "expired_missing_expires_at": _category(
            session,
            ordered.where(Memory.status == "expired", Memory.expires_at.is_(None)),
            detail_limit,
        ),
        "non_active_with_embedding": _category(
            session,
            with_embedding.where(Memory.status != "active"),
            detail_limit,
        ),
    }
