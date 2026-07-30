"""SQL selection and persistence primitives for explicit embedding batches."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.memory_embedding import MemoryEmbedding


def select_candidates(
    session: Session, *, scope: str, project_id: uuid.UUID | None, limit: int
) -> list[Memory]:
    """Select active rows missing embeddings in stable creation order."""

    statement = (
        select(Memory)
        .outerjoin(MemoryEmbedding)
        .where(Memory.status == "active", MemoryEmbedding.id.is_(None))
    )
    if scope == "project":
        statement = statement.where(Memory.project_id == project_id)
    elif scope == "unassigned":
        statement = statement.where(Memory.project_id.is_(None))
    return list(
        session.scalars(statement.order_by(Memory.created_at, Memory.id).limit(limit))
    )


def lock_memories(
    session: Session, memory_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Memory]:
    """Lock selected Memory rows in UUID order without committing."""

    rows = session.scalars(
        select(Memory)
        .where(Memory.id.in_(memory_ids))
        .order_by(Memory.id)
        .with_for_update()
    )
    return {row.id: row for row in rows}


def embeddings_for(
    session: Session, memory_ids: list[uuid.UUID]
) -> dict[uuid.UUID, MemoryEmbedding]:
    rows = session.scalars(
        select(MemoryEmbedding).where(MemoryEmbedding.memory_id.in_(memory_ids))
    )
    return {row.memory_id: row for row in rows}


def insert_embedding_if_missing(
    session: Session,
    *,
    memory_id: uuid.UUID,
    provider: str,
    model: str,
    dimensions: int,
    embedding: list[float],
    input_hash: str,
    embedded_at: datetime,
) -> tuple[MemoryEmbedding, bool]:
    """Insert once defensively and return the winning row without committing."""

    statement = (
        insert(MemoryEmbedding)
        .values(
            memory_id=memory_id,
            provider=provider,
            model=model,
            dimensions=dimensions,
            embedding=embedding,
            input_hash=input_hash,
            embedded_at=embedded_at,
        )
        .on_conflict_do_nothing(index_elements=[MemoryEmbedding.memory_id])
        .returning(MemoryEmbedding)
    )
    created = session.scalars(statement).one_or_none()
    if created is not None:
        return created, True
    existing = session.scalar(
        select(MemoryEmbedding).where(MemoryEmbedding.memory_id == memory_id)
    )
    if existing is None:  # pragma: no cover - defensive impossible database state
        raise RuntimeError("embedding conflict winner missing")
    return existing, False
