"""Persistence operations for memories."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, literal, select, union
from sqlalchemy.orm import Session

from app.memory_quality.normalization import EXACT_WHITESPACE_PATTERN
from app.models.memory import Memory
from app.models.memory_embedding import MemoryEmbedding
from app.models.project import Project
from app.schemas.memory import MemoryCreate, MemoryStatus, MemoryType

RRF_K = 60


@dataclass(frozen=True)
class ScoredMemory:
    memory: Memory
    lexical_score: float | None
    semantic_score: float | None


@dataclass(frozen=True)
class ExplainedMemorySearchResult:
    """Immutable repository projection for one explained ranked result."""

    rank: int
    memory: Memory
    lexical_rank: int | None
    semantic_rank: int | None
    lexical_score: float | None
    semantic_distance: float | None
    lexical_rrf_contribution: float | None
    semantic_rrf_contribution: float | None
    fused_rrf_score: float | None


def _lexical_ranking(query: str) -> tuple[Any, Any, tuple[Any, ...]]:
    """Return the canonical lexical query, score, and deterministic ordering."""

    search_query = func.websearch_to_tsquery("simple", query)
    score = func.ts_rank_cd(Memory.search_vector, search_query)
    order = (score.desc(), Memory.created_at.desc(), Memory.id.asc())
    return search_query, score, order


def _semantic_ranking(query_vector: list[float]) -> tuple[Any, tuple[Any, ...]]:
    """Return the canonical cosine distance and deterministic ordering."""

    distance = MemoryEmbedding.embedding.cosine_distance(query_vector)
    order = (distance.asc(), Memory.created_at.desc(), Memory.id.asc())
    return distance, order


def _hybrid_candidate_limit(*, limit: int, offset: int) -> int:
    """Return the established bounded candidate window for both channels."""

    return min(1000, max(100, (limit + offset) * 5))


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
        search_query, rank, lexical_order = _lexical_ranking(query)
        statement = statement.where(Memory.search_vector.bool_op("@@")(search_query))
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
        statement = statement.order_by(*lexical_order)
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

    _distance, semantic_order = _semantic_ranking(query_vector)
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
    statement = statement.order_by(*semantic_order)
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

    candidate_limit = _hybrid_candidate_limit(limit=limit, offset=offset)

    search_query, _lexical_score, lexical_order = _lexical_ranking(query)
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

    _distance, semantic_order = _semantic_ranking(query_vector)
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
            literal(1.0) / (literal(RRF_K) + lexical_candidates.c.lexical_rank),
            0.0,
        )
        + func.coalesce(
            literal(1.0) / (literal(RRF_K) + semantic_candidates.c.semantic_rank),
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


def search_memories_explained(
    session: Session,
    *,
    query: str,
    mode: str,
    query_vector: list[float] | None = None,
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
) -> list[ExplainedMemorySearchResult]:
    """Return one SQL-filtered, ranked, fused, and paginated explained page."""

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

    search_query, lexical_score, lexical_order = _lexical_ranking(query)
    lexical = apply_filters(
        select(
            Memory.id.label("memory_id"),
            lexical_score.label("lexical_score"),
            func.row_number().over(order_by=lexical_order).label("lexical_rank"),
        ).where(Memory.search_vector.bool_op("@@")(search_query))
    )

    if mode == "lexical":
        ranked = lexical.cte("lexical_ranked")
        statement = (
            select(Memory, ranked.c.lexical_rank, ranked.c.lexical_score)
            .join(ranked, ranked.c.memory_id == Memory.id)
            .order_by(ranked.c.lexical_rank)
            .offset(offset)
            .limit(limit)
        )
        return [
            ExplainedMemorySearchResult(
                rank=int(row.lexical_rank),
                memory=row.Memory,
                lexical_rank=int(row.lexical_rank),
                semantic_rank=None,
                lexical_score=float(row.lexical_score),
                semantic_distance=None,
                lexical_rrf_contribution=None,
                semantic_rrf_contribution=None,
                fused_rrf_score=None,
            )
            for row in session.execute(statement)
        ]

    if query_vector is None:
        raise ValueError("query_vector is required for semantic search")
    distance, semantic_order = _semantic_ranking(query_vector)
    semantic = apply_filters(
        select(
            Memory.id.label("memory_id"),
            distance.label("semantic_distance"),
            func.row_number().over(order_by=semantic_order).label("semantic_rank"),
        ).join(MemoryEmbedding)
    )
    if mode == "semantic":
        ranked = semantic.cte("semantic_ranked")
        statement = (
            select(Memory, ranked.c.semantic_rank, ranked.c.semantic_distance)
            .join(ranked, ranked.c.memory_id == Memory.id)
            .order_by(ranked.c.semantic_rank)
            .offset(offset)
            .limit(limit)
        )
        return [
            ExplainedMemorySearchResult(
                rank=int(row.semantic_rank),
                memory=row.Memory,
                lexical_rank=None,
                semantic_rank=int(row.semantic_rank),
                lexical_score=None,
                semantic_distance=float(row.semantic_distance),
                lexical_rrf_contribution=None,
                semantic_rrf_contribution=None,
                fused_rrf_score=None,
            )
            for row in session.execute(statement)
        ]

    candidate_limit = _hybrid_candidate_limit(limit=limit, offset=offset)
    lexical_candidates = (
        lexical.order_by(*lexical_order)
        .limit(candidate_limit)
        .cte("lexical_candidates")
    )
    semantic_candidates = (
        semantic.order_by(*semantic_order)
        .limit(candidate_limit)
        .cte("semantic_candidates")
    )
    candidate_ids = union(
        select(lexical_candidates.c.memory_id),
        select(semantic_candidates.c.memory_id),
    ).cte("candidate_ids")
    lexical_contribution = (
        literal(1.0) / (literal(RRF_K) + lexical_candidates.c.lexical_rank)
    ).label("lexical_rrf_contribution")
    semantic_contribution = (
        literal(1.0) / (literal(RRF_K) + semantic_candidates.c.semantic_rank)
    ).label("semantic_rrf_contribution")
    fused_score = (
        func.coalesce(lexical_contribution, 0.0)
        + func.coalesce(semantic_contribution, 0.0)
    ).label("fused_rrf_score")
    fused = (
        select(
            candidate_ids.c.memory_id,
            lexical_candidates.c.lexical_rank,
            semantic_candidates.c.semantic_rank,
            lexical_candidates.c.lexical_score,
            semantic_candidates.c.semantic_distance,
            lexical_contribution,
            semantic_contribution,
            fused_score,
        )
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
    final_order = (
        fused.c.fused_rrf_score.desc(),
        Memory.created_at.desc(),
        Memory.id.asc(),
    )
    final_ranked = (
        select(
            fused,
            func.row_number().over(order_by=final_order).label("result_rank"),
        )
        .join(Memory, Memory.id == fused.c.memory_id)
        .cte("final_ranked")
    )
    statement = (
        select(Memory, final_ranked)
        .join(final_ranked, final_ranked.c.memory_id == Memory.id)
        .order_by(final_ranked.c.result_rank)
        .offset(offset)
        .limit(limit)
    )
    return [
        ExplainedMemorySearchResult(
            rank=int(row.result_rank),
            memory=row.Memory,
            lexical_rank=int(row.lexical_rank)
            if row.lexical_rank is not None
            else None,
            semantic_rank=int(row.semantic_rank)
            if row.semantic_rank is not None
            else None,
            lexical_score=float(row.lexical_score)
            if row.lexical_score is not None
            else None,
            semantic_distance=float(row.semantic_distance)
            if row.semantic_distance is not None
            else None,
            lexical_rrf_contribution=float(row.lexical_rrf_contribution)
            if row.lexical_rrf_contribution is not None
            else None,
            semantic_rrf_contribution=float(row.semantic_rrf_contribution)
            if row.semantic_rrf_contribution is not None
            else None,
            fused_rrf_score=float(row.fused_rrf_score),
        )
        for row in session.execute(statement)
    ]


def search_answer_evidence(
    session: Session,
    *,
    query: str,
    mode: str,
    project_id: uuid.UUID | None,
    limit: int,
    query_vector: list[float] | None,
) -> list[ScoredMemory]:
    """Retrieve one bounded, active-only scored evidence set."""

    project_filter = Memory.project_id == project_id if project_id is not None else None
    active_filters = [Memory.status == "active"]
    if project_filter is not None:
        active_filters.append(project_filter)
    search_query = func.websearch_to_tsquery("simple", query)
    lexical_score = func.ts_rank_cd(Memory.search_vector, search_query)

    if mode == "lexical":
        statement = (
            select(Memory, lexical_score)
            .where(Memory.search_vector.bool_op("@@")(search_query), *active_filters)
            .order_by(lexical_score.desc(), Memory.created_at.desc(), Memory.id.asc())
            .limit(limit)
        )
        return [
            ScoredMemory(row[0], float(row[1]), None)
            for row in session.execute(statement)
        ]

    if query_vector is None:
        raise ValueError("semantic retrieval requires a query vector")
    distance = MemoryEmbedding.embedding.cosine_distance(query_vector)
    semantic_score = (literal(1.0) - distance).label("semantic_score")
    if mode == "semantic":
        statement = (
            select(Memory, semantic_score)
            .join(MemoryEmbedding)
            .where(*active_filters)
            .order_by(distance.asc(), Memory.created_at.desc(), Memory.id.asc())
            .limit(limit)
        )
        return [
            ScoredMemory(row[0], None, float(row[1]))
            for row in session.execute(statement)
        ]

    candidate_limit = min(1000, max(100, limit * 5))
    lexical_order = (lexical_score.desc(), Memory.created_at.desc(), Memory.id.asc())
    lexical = (
        select(
            Memory.id.label("memory_id"),
            lexical_score.label("lexical_score"),
            func.row_number().over(order_by=lexical_order).label("lexical_rank"),
        )
        .where(Memory.search_vector.bool_op("@@")(search_query), *active_filters)
        .order_by(*lexical_order)
        .limit(candidate_limit)
        .cte("answer_lexical")
    )
    semantic_order = (distance.asc(), Memory.created_at.desc(), Memory.id.asc())
    semantic = (
        select(
            Memory.id.label("memory_id"),
            semantic_score,
            func.row_number().over(order_by=semantic_order).label("semantic_rank"),
        )
        .join(MemoryEmbedding)
        .where(*active_filters)
        .order_by(*semantic_order)
        .limit(candidate_limit)
        .cte("answer_semantic")
    )
    ids = union(select(lexical.c.memory_id), select(semantic.c.memory_id)).cte(
        "answer_ids"
    )
    rrf = func.coalesce(
        literal(1.0) / (literal(60) + lexical.c.lexical_rank), 0.0
    ) + func.coalesce(literal(1.0) / (literal(60) + semantic.c.semantic_rank), 0.0)
    statement = (
        select(Memory, lexical.c.lexical_score, semantic.c.semantic_score)
        .join(ids, ids.c.memory_id == Memory.id)
        .outerjoin(lexical, lexical.c.memory_id == ids.c.memory_id)
        .outerjoin(semantic, semantic.c.memory_id == ids.c.memory_id)
        .order_by(rrf.desc(), Memory.created_at.desc(), Memory.id.asc())
        .limit(limit)
    )
    return [
        ScoredMemory(
            row[0],
            float(row[1]) if row[1] is not None else None,
            float(row[2]) if row[2] is not None else None,
        )
        for row in session.execute(statement)
    ]


def get_memory(session: Session, memory_id: uuid.UUID) -> Memory | None:
    """Return a memory by identifier, or None when it does not exist."""

    return session.scalar(select(Memory).where(Memory.id == memory_id))


def lock_memories(
    session: Session, memory_ids: set[uuid.UUID]
) -> dict[uuid.UUID, Memory]:
    """Lock requested Memory rows in deterministic UUID order."""

    statement = (
        select(Memory)
        .where(Memory.id.in_(memory_ids))
        .order_by(Memory.id.asc())
        .with_for_update()
    )
    return {memory.id: memory for memory in session.scalars(statement).all()}


def lock_memory(session: Session, memory_id: uuid.UUID) -> Memory | None:
    """Lock one Memory row for a caller-owned transition transaction."""

    return session.scalar(
        select(Memory).where(Memory.id == memory_id).with_for_update()
    )


def lock_memory_successors(session: Session, older_id: uuid.UUID) -> list[Memory]:
    """Lock direct successors after the caller has serialized on the older row."""

    statement = (
        select(Memory)
        .where(Memory.supersedes_id == older_id)
        .order_by(Memory.id.asc())
        .with_for_update()
    )
    return list(session.scalars(statement).all())


def predecessor_chain_contains(
    session: Session, *, start_id: uuid.UUID, sought_id: uuid.UUID
) -> bool:
    """Return whether sought_id occurs in the complete predecessor ancestry."""

    ancestry = (
        select(Memory.id, Memory.supersedes_id)
        .where(Memory.id == start_id)
        .cte("memory_ancestry", recursive=True)
    )
    parent = Memory.__table__.alias("memory_parent")
    ancestry = ancestry.union(
        select(parent.c.id, parent.c.supersedes_id).join(
            ancestry, parent.c.id == ancestry.c.supersedes_id
        )
    )
    statement = select(ancestry.c.id).where(ancestry.c.id == sought_id).limit(1)
    return session.scalar(statement) is not None


def apply_memory_supersession(*, older: Memory, replacement: Memory) -> None:
    """Apply the two intentional model changes without flushing or committing."""

    replacement.supersedes_id = older.id
    older.status = "superseded"


def apply_memory_expiration(*, memory: Memory, expires_at: datetime) -> None:
    """Apply only the intentional expiration fields without committing."""

    memory.status = "expired"
    memory.expires_at = expires_at


def apply_memory_quality_refinement(
    *, memory: Memory, confidence: float | None, importance: float | None
) -> None:
    """Apply only supplied quality values without flushing or committing."""

    if confidence is not None and confidence != memory.confidence:
        memory.confidence = confidence
    if importance is not None and importance != memory.importance:
        memory.importance = importance


def get_memory_embedding(
    session: Session, memory_id: uuid.UUID
) -> MemoryEmbedding | None:
    """Return one stored embedding record without generating derived data."""

    return session.scalar(
        select(MemoryEmbedding).where(MemoryEmbedding.memory_id == memory_id)
    )


def list_exact_duplicate_candidates(
    session: Session,
    *,
    target: Memory,
    normalized_content: str,
    limit: int,
) -> list[Memory]:
    """Find active, same-scope Memories with conservatively normalized content."""

    database_normalized = func.regexp_replace(
        Memory.content, EXACT_WHITESPACE_PATTERN, " ", "g"
    )
    database_normalized = func.btrim(database_normalized, " \t\n\r\f\v")
    statement = (
        select(Memory)
        .where(
            Memory.id != target.id,
            Memory.project_id.is_not_distinct_from(target.project_id),
            Memory.status == "active",
            database_normalized == normalized_content,
        )
        .order_by(Memory.id.asc())
        .limit(limit)
    )
    return list(session.scalars(statement).all())


def list_lexical_similarity_candidates(
    session: Session,
    *,
    target: Memory,
    query: str,
    limit: int,
) -> list[Memory]:
    """Return a bounded lexical candidate pool for deterministic classification."""

    search_query = func.websearch_to_tsquery("simple", query)
    rank = func.ts_rank_cd(Memory.search_vector, search_query)
    statement = (
        select(Memory)
        .where(
            Memory.id != target.id,
            Memory.project_id.is_not_distinct_from(target.project_id),
            Memory.status == "active",
            Memory.search_vector.bool_op("@@")(search_query),
        )
        .order_by(rank.desc(), Memory.id.asc())
        .limit(limit)
    )
    return list(session.scalars(statement).all())


def list_semantic_similarity_candidates(
    session: Session,
    *,
    target: Memory,
    query_vector: list[float],
    provider: str,
    model: str,
    dimensions: int,
    limit: int,
) -> list[tuple[Memory, float | None]]:
    """Return a bounded stored-vector candidate pool with cosine similarities."""

    distance = MemoryEmbedding.embedding.cosine_distance(query_vector)
    statement = (
        select(Memory, (literal(1.0) - distance).label("similarity"))
        .join(MemoryEmbedding)
        .where(
            Memory.id != target.id,
            Memory.project_id.is_not_distinct_from(target.project_id),
            Memory.status == "active",
            MemoryEmbedding.provider == provider,
            MemoryEmbedding.model == model,
            MemoryEmbedding.dimensions == dimensions,
        )
        .order_by(distance.asc(), Memory.id.asc())
        .limit(limit)
    )
    return [
        (row[0], float(row[1]) if row[1] is not None else None)
        for row in session.execute(statement).all()
    ]
