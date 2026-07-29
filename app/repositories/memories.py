"""Persistence operations for memories."""

import uuid
from datetime import datetime

from sqlalchemy import Select, func, literal, select, union
from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.memory_embedding import MemoryEmbedding
from app.models.project import Project
from app.schemas.memory import MemoryCreate, MemoryStatus, MemoryType


def _apply_structured_filters(
    statement: Select[tuple[Memory]],
    *,
    project_id: uuid.UUID | None,
    memory_type: MemoryType | None,
    status: MemoryStatus | None,
    importance_min: float | None,
    importance_max: float | None,
    confidence_min: float | None,
    confidence_max: float | None,
    event_time_from: datetime | None,
    event_time_to: datetime | None,
    created_at_from: datetime | None,
    created_at_to: datetime | None,
) -> Select[tuple[Memory]]:
    """Apply the canonical Memory structured predicates to a statement."""

    values = (
        (project_id, Memory.project_id, "eq"),
        (memory_type, Memory.memory_type, "eq"),
        (status, Memory.status, "eq"),
        (importance_min, Memory.importance, "ge"),
        (importance_max, Memory.importance, "le"),
        (confidence_min, Memory.confidence, "ge"),
        (confidence_max, Memory.confidence, "le"),
        (event_time_from, Memory.event_time, "ge"),
        (event_time_to, Memory.event_time, "le"),
        (created_at_from, Memory.created_at, "ge"),
        (created_at_to, Memory.created_at, "le"),
    )
    for value, column, operation in values:
        if value is None:
            continue
        if operation == "eq":
            statement = statement.where(column == value)
        elif operation == "ge":
            statement = statement.where(column >= value)
        else:
            statement = statement.where(column <= value)
    return statement


def project_exists(session: Session, project_id: uuid.UUID) -> bool:
    """Return whether the project identifier exists."""

    statement = select(Project.id).where(Project.id == project_id)
    return session.scalar(statement) is not None


def create_memory(session: Session, memory_data: MemoryCreate) -> Memory:
    """Add and flush a Memory without committing its transaction."""

    memory = Memory(**memory_data.model_dump())
    session.add(memory)
    session.flush()
    session.refresh(memory)
    return memory


def list_memories(
    session: Session,
    *,
    project_id: uuid.UUID | None,
    query: str | None = None,
    memory_type: MemoryType | None = None,
    status: MemoryStatus | None = None,
    importance_min: float | None = None,
    importance_max: float | None = None,
    confidence_min: float | None = None,
    confidence_max: float | None = None,
    event_time_from: datetime | None = None,
    event_time_to: datetime | None = None,
    created_at_from: datetime | None = None,
    created_at_to: datetime | None = None,
    limit: int,
    offset: int,
) -> list[Memory]:
    """Return a deterministic, SQL-filtered page of memories."""

    statement = select(Memory)
    rank = None
    if query is not None:
        search_query = func.websearch_to_tsquery("simple", query)
        statement = statement.where(Memory.search_vector.bool_op("@@")(search_query))
        rank = func.ts_rank_cd(Memory.search_vector, search_query)
    statement = _apply_structured_filters(
        statement,
        project_id=project_id,
        memory_type=memory_type,
        status=status,
        importance_min=importance_min,
        importance_max=importance_max,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        event_time_from=event_time_from,
        event_time_to=event_time_to,
        created_at_from=created_at_from,
        created_at_to=created_at_to,
    )
    if rank is not None:
        statement = statement.order_by(
            rank.desc(), Memory.created_at.desc(), Memory.id.asc()
        )
    else:
        statement = statement.order_by(Memory.created_at.desc(), Memory.id.asc())
    statement = statement.limit(limit).offset(offset)
    return list(session.scalars(statement).all())


def search_memories(
    session: Session,
    *,
    query_vector: list[float],
    project_id: uuid.UUID | None = None,
    memory_type: MemoryType | None = None,
    status: MemoryStatus | None = None,
    importance_min: float | None = None,
    importance_max: float | None = None,
    confidence_min: float | None = None,
    confidence_max: float | None = None,
    event_time_from: datetime | None = None,
    event_time_to: datetime | None = None,
    created_at_from: datetime | None = None,
    created_at_to: datetime | None = None,
    limit: int,
    offset: int,
) -> list[Memory]:
    """Return one SQL-ranked page of Memories with stored embeddings."""

    distance = MemoryEmbedding.embedding.cosine_distance(query_vector)
    statement = select(Memory).join(MemoryEmbedding)
    statement = _apply_structured_filters(
        statement,
        project_id=project_id,
        memory_type=memory_type,
        status=status,
        importance_min=importance_min,
        importance_max=importance_max,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        event_time_from=event_time_from,
        event_time_to=event_time_to,
        created_at_from=created_at_from,
        created_at_to=created_at_to,
    )
    statement = statement.order_by(
        distance.asc(), Memory.created_at.desc(), Memory.id.asc()
    )
    return list(session.scalars(statement.offset(offset).limit(limit)).all())


def search_memories_hybrid(
    session: Session,
    *,
    query: str,
    query_vector: list[float],
    project_id: uuid.UUID | None = None,
    memory_type: MemoryType | None = None,
    status: MemoryStatus | None = None,
    importance_min: float | None = None,
    importance_max: float | None = None,
    confidence_min: float | None = None,
    confidence_max: float | None = None,
    event_time_from: datetime | None = None,
    event_time_to: datetime | None = None,
    created_at_from: datetime | None = None,
    created_at_to: datetime | None = None,
    limit: int,
    offset: int,
) -> list[Memory]:
    """Fuse bounded lexical and semantic candidate ranks in one SQL statement."""

    def apply_filters(statement: Select[tuple[Memory]]) -> Select[tuple[Memory]]:
        return _apply_structured_filters(
            statement,
            project_id=project_id,
            memory_type=memory_type,
            status=status,
            importance_min=importance_min,
            importance_max=importance_max,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            event_time_from=event_time_from,
            event_time_to=event_time_to,
            created_at_from=created_at_from,
            created_at_to=created_at_to,
        )

    candidate_limit = min(1000, max(100, (limit + offset) * 5))

    search_query = func.websearch_to_tsquery("simple", query)
    lexical_score = func.ts_rank_cd(Memory.search_vector, search_query)
    lexical_order = (lexical_score.desc(), Memory.created_at.desc(), Memory.id.asc())
    lexical = select(
        Memory.id.label("memory_id"),
        func.row_number().over(order_by=lexical_order).label("lexical_rank"),
    ).where(Memory.search_vector.bool_op("@@")(search_query))
    lexical = apply_filters(lexical)
    lexical_candidates = (
        lexical.order_by(*lexical_order)
        .limit(candidate_limit)
        .cte("lexical_candidates")
    )

    distance = MemoryEmbedding.embedding.cosine_distance(query_vector)
    semantic_order = (distance.asc(), Memory.created_at.desc(), Memory.id.asc())
    semantic = select(
        Memory.id.label("memory_id"),
        func.row_number().over(order_by=semantic_order).label("semantic_rank"),
    ).join(MemoryEmbedding)
    semantic = apply_filters(semantic)
    semantic_candidates = (
        semantic.order_by(*semantic_order)
        .limit(candidate_limit)
        .cte("semantic_candidates")
    )

    candidate_ids = union(
        select(lexical_candidates.c.memory_id),
        select(semantic_candidates.c.memory_id),
    ).cte("candidate_ids")
    rrf_score = (
        func.coalesce(
            literal(1.0) / (literal(60) + lexical_candidates.c.lexical_rank),
            0.0,
        )
        + func.coalesce(
            literal(1.0) / (literal(60) + semantic_candidates.c.semantic_rank),
            0.0,
        )
    ).label("rrf_score")
    fused = (
        select(candidate_ids.c.memory_id, rrf_score)
        .outerjoin(
            lexical_candidates,
            lexical_candidates.c.memory_id == candidate_ids.c.memory_id,
        )
        .outerjoin(
            semantic_candidates,
            semantic_candidates.c.memory_id == candidate_ids.c.memory_id,
        )
        .cte("fused_candidates")
    )
    statement = (
        select(Memory)
        .join(fused, fused.c.memory_id == Memory.id)
        .order_by(fused.c.rrf_score.desc(), Memory.created_at.desc(), Memory.id.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(session.scalars(statement).all())


def get_memory(session: Session, memory_id: uuid.UUID) -> Memory | None:
    """Return a memory by identifier, or None when it does not exist."""

    return session.scalar(select(Memory).where(Memory.id == memory_id))
