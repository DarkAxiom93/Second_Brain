"""Memory creation and retrieval endpoints."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_session
from app.embeddings import (
    EmbeddingProvider,
    InvalidEmbeddingResponseError,
    ProviderRequestError,
    ProviderUnavailableError,
    get_embedding_provider,
)
from app.embeddings.openai_provider import validate_embedding
from app.memory_quality.contradiction import detect_memory_contradictions
from app.memory_quality.expiration import ExpirationConflict, classify_expiration
from app.memory_quality.refinement import (
    QualityRefinementConflict,
    classify_quality_refinement,
)
from app.memory_quality.similarity import detect_similar_memories
from app.memory_quality.supersession import (
    SupersessionConflict,
    classify_supersession,
)
from app.models.memory import Memory
from app.models.memory_source import MemorySource
from app.repositories import memories as memory_repository
from app.repositories import memory_embeddings as embedding_repository
from app.repositories import sources as source_repository
from app.schemas.memory import (
    ExplainedMemorySearchMode,
    ExplainedMemorySearchRequest,
    ExplainedMemorySearchResultRead,
    MemoryContradictionCandidateRead,
    MemoryContradictionRead,
    MemoryCreate,
    MemoryExpirationRead,
    MemoryFilters,
    MemoryQualityRefinementRead,
    MemoryQualityRefinementRequest,
    MemoryRead,
    MemorySearchChannel,
    MemorySearchExplanationRead,
    MemorySearchRequest,
    MemorySimilarityCandidateRead,
    MemorySimilarityRead,
    MemorySupersedeRequest,
    MemorySupersessionRead,
)
from app.schemas.memory_embedding import MemoryEmbeddingRead
from app.schemas.source import (
    LinkedSourceRead,
    MemorySourceLinkCreate,
    MemorySourceRead,
)

router = APIRouter(prefix="/memories", tags=["memories"])
PUBLIC_RANKING_PRECISION = 6


def provider_dependency() -> EmbeddingProvider:
    """Resolve provider while translating unavailable configuration safely."""

    try:
        return get_embedding_provider()
    except ProviderUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="embedding provider unavailable",
        ) from None


def provider_resolver_dependency() -> Callable[[], EmbeddingProvider]:
    """Inject a lazy resolver so lexical explained search never resolves a provider."""

    return provider_dependency


def database_unavailable() -> HTTPException:
    """Build the public database-failure response."""

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="database unavailable",
    )


def _public_round(value: float | None) -> float | None:
    return None if value is None else round(value, PUBLIC_RANKING_PRECISION)


def _explained_result_read(
    item: memory_repository.ExplainedMemorySearchResult,
    mode: ExplainedMemorySearchMode,
) -> ExplainedMemorySearchResultRead:
    lexical_signal = (
        None
        if item.lexical_score is None
        else _public_round(
            max(0.0, min(1.0, item.lexical_score / (1.0 + item.lexical_score)))
        )
    )
    semantic_signal = (
        None
        if item.semantic_distance is None
        else _public_round(max(0.0, min(1.0, 1.0 - (item.semantic_distance / 2.0))))
    )
    matched_by: list[MemorySearchChannel] = []
    if item.lexical_rank is not None:
        matched_by.append("lexical")
    if item.semantic_rank is not None:
        matched_by.append("semantic")
    return ExplainedMemorySearchResultRead(
        rank=item.rank,
        memory=MemoryRead.model_validate(item.memory),
        explanation=MemorySearchExplanationRead(
            mode=mode,
            matched_by=matched_by,
            lexical_rank=item.lexical_rank,
            semantic_rank=item.semantic_rank,
            lexical_signal=lexical_signal,
            semantic_signal=semantic_signal,
            lexical_rrf_contribution=_public_round(item.lexical_rrf_contribution),
            semantic_rrf_contribution=_public_round(item.semantic_rrf_contribution),
            fused_rrf_score=_public_round(item.fused_rrf_score),
        ),
    )


@router.post(
    "/{memory_id}/quality",
    response_model=MemoryQualityRefinementRead,
    responses={
        404: {"description": "Memory not found"},
        409: {"description": "Memory quality-refinement conflict"},
        503: {"description": "Database unavailable"},
    },
)
def refine_memory_quality(
    memory_id: uuid.UUID,
    request: MemoryQualityRefinementRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> MemoryQualityRefinementRead:
    """Explicitly refine confidence and/or importance on one active Memory."""

    try:
        memory = memory_repository.lock_memory(session, memory_id)
        if memory is None:
            session.rollback()
            raise HTTPException(status_code=404, detail="memory not found")
        refinement = classify_quality_refinement(
            memory=memory,
            confidence=request.confidence,
            importance=request.importance,
        )
        if refinement == "unchanged":
            result = MemoryQualityRefinementRead(
                refinement_status=refinement,
                memory=MemoryRead.model_validate(memory),
            )
            session.rollback()
            return result
        memory_repository.apply_memory_quality_refinement(
            memory=memory,
            confidence=request.confidence,
            importance=request.importance,
        )
        session.commit()
        session.refresh(memory)
    except QualityRefinementConflict as conflict:
        session.rollback()
        raise HTTPException(status_code=409, detail=conflict.detail) from None
    except SQLAlchemyError:
        session.rollback()
        raise database_unavailable() from None
    return MemoryQualityRefinementRead(
        refinement_status=refinement,
        memory=MemoryRead.model_validate(memory),
    )


@router.post(
    "/{memory_id}/expire",
    response_model=MemoryExpirationRead,
    responses={
        404: {"description": "Memory not found"},
        409: {"description": "Memory expiration conflict"},
        503: {"description": "Database unavailable"},
    },
)
def expire_memory(
    memory_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> MemoryExpirationRead:
    """Explicitly expire one active Memory."""

    captured_at = datetime.now(UTC)
    try:
        memory = memory_repository.lock_memory(session, memory_id)
        if memory is None:
            session.rollback()
            raise HTTPException(status_code=404, detail="memory not found")
        decision = classify_expiration(memory=memory, captured_at=captured_at)
        if decision.status == "updated":
            memory_repository.apply_memory_expiration(
                memory=memory, expires_at=decision.expires_at
            )
        session.commit()
        if decision.status == "updated":
            session.refresh(memory)
    except ExpirationConflict as conflict:
        session.rollback()
        raise HTTPException(status_code=409, detail=conflict.detail) from None
    except SQLAlchemyError:
        session.rollback()
        raise database_unavailable() from None
    return MemoryExpirationRead(
        expiration_status=decision.status,
        memory=MemoryRead.model_validate(memory),
    )


@router.post(
    "/{memory_id}/supersede",
    response_model=MemorySupersessionRead,
    responses={
        404: {"description": "Memory not found"},
        409: {"description": "Supersession conflict"},
        503: {"description": "Database unavailable"},
    },
)
def supersede_memory(
    memory_id: uuid.UUID,
    request: MemorySupersedeRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> MemorySupersessionRead:
    """Explicitly supersede an older Memory with an existing replacement."""

    if memory_id == request.replacement_memory_id:
        session.rollback()
        raise HTTPException(status_code=409, detail="memory cannot supersede itself")
    try:
        locked = memory_repository.lock_memories(
            session, {memory_id, request.replacement_memory_id}
        )
        older = locked.get(memory_id)
        replacement = locked.get(request.replacement_memory_id)
        if older is None:
            session.rollback()
            raise HTTPException(status_code=404, detail="older memory not found")
        if replacement is None:
            session.rollback()
            raise HTTPException(status_code=404, detail="replacement memory not found")
        successors = memory_repository.lock_memory_successors(session, older.id)
        creates_cycle = memory_repository.predecessor_chain_contains(
            session, start_id=older.id, sought_id=replacement.id
        )
        transition = classify_supersession(
            older=older,
            replacement=replacement,
            existing_successors=successors,
            creates_cycle=creates_cycle,
        )
        if transition == "updated":
            memory_repository.apply_memory_supersession(
                older=older, replacement=replacement
            )
        session.commit()
        if transition == "updated":
            session.refresh(older)
            session.refresh(replacement)
    except SupersessionConflict as conflict:
        session.rollback()
        raise HTTPException(status_code=409, detail=conflict.detail) from None
    except SQLAlchemyError:
        session.rollback()
        raise database_unavailable() from None
    return MemorySupersessionRead(
        supersession_status=transition,
        superseded_memory=MemoryRead.model_validate(older),
        replacement_memory=MemoryRead.model_validate(replacement),
    )


@router.get(
    "/{memory_id}/contradictions",
    response_model=MemoryContradictionRead,
    responses={
        404: {"description": "Memory not found"},
        503: {"description": "Database unavailable"},
    },
)
def get_memory_contradictions(
    memory_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> MemoryContradictionRead:
    """Return bounded English-only explicit-polarity evidence without mutation."""

    try:
        target = memory_repository.get_memory(session, memory_id)
        if target is None or target.status != "active":
            raise HTTPException(status_code=404, detail="memory not found")
        candidates = detect_memory_contradictions(session, target=target, limit=limit)
    except SQLAlchemyError:
        raise database_unavailable() from None
    return MemoryContradictionRead(
        target_memory_id=target.id,
        candidates=[
            MemoryContradictionCandidateRead(
                memory_id=item.memory.id,
                classification=item.classification,
                evidence_type=item.evidence_type,
                reason=item.reason,
                lexical_similarity=item.lexical_similarity,
                semantic_similarity=item.semantic_similarity,
                target_state=item.target_state,
                candidate_state=item.candidate_state,
            )
            for item in candidates
        ],
    )


@router.get(
    "/{memory_id}/similarities",
    response_model=MemorySimilarityRead,
    responses={
        404: {"description": "Memory not found"},
        503: {"description": "Database unavailable"},
    },
)
def get_memory_similarities(
    memory_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> MemorySimilarityRead:
    """Return advisory duplicate and similarity candidates without mutations."""

    try:
        target = memory_repository.get_memory(session, memory_id)
        if target is None:
            raise HTTPException(status_code=404, detail="memory not found")
        candidates = detect_similar_memories(session, target=target, limit=limit)
    except SQLAlchemyError:
        raise database_unavailable() from None
    return MemorySimilarityRead(
        target_memory_id=target.id,
        candidates=[
            MemorySimilarityCandidateRead(
                memory_id=item.memory.id,
                classification=item.classification,
                lexical_similarity=item.lexical_similarity,
                semantic_similarity=item.semantic_similarity,
                reason=item.reason,
            )
            for item in candidates
        ],
    )


@router.post("/search/explained", response_model=list[ExplainedMemorySearchResultRead])
def search_memories_explained(
    request: ExplainedMemorySearchRequest,
    session: Annotated[Session, Depends(get_db_session)],
    resolve_provider: Annotated[
        Callable[[], EmbeddingProvider], Depends(provider_resolver_dependency)
    ],
) -> list[ExplainedMemorySearchResultRead]:
    """Return bounded deterministic ranking explanations without persistence."""

    query_vector = None
    if request.mode in ("semantic", "hybrid"):
        try:
            provider = resolve_provider()
            query_vector = validate_embedding(provider.embed(request.query), 1536)
        except ProviderUnavailableError:
            raise HTTPException(
                status_code=503, detail="embedding provider unavailable"
            ) from None
        except InvalidEmbeddingResponseError:
            raise HTTPException(
                status_code=502, detail="invalid embedding response"
            ) from None
        except ProviderRequestError:
            raise HTTPException(
                status_code=502, detail="embedding provider failed"
            ) from None
    try:
        results = memory_repository.search_memories_explained(
            session,
            query=request.query,
            mode=request.mode,
            query_vector=query_vector,
            **request.filters.model_dump(),
            **request.pagination.model_dump(),
        )
    except SQLAlchemyError:
        raise database_unavailable() from None
    return [_explained_result_read(item, request.mode) for item in results]


@router.post("/search", response_model=list[MemoryRead])
def search_memories(
    request: MemorySearchRequest,
    session: Annotated[Session, Depends(get_db_session)],
    provider: Annotated[EmbeddingProvider, Depends(provider_dependency)],
) -> list[Memory]:
    """Search Memories with semantic ranking or hybrid rank fusion."""

    try:
        query_vector = validate_embedding(provider.embed(request.query), 1536)
    except InvalidEmbeddingResponseError:
        raise HTTPException(
            status_code=502, detail="invalid embedding response"
        ) from None
    except ProviderRequestError:
        raise HTTPException(
            status_code=502, detail="embedding provider failed"
        ) from None
    try:
        search = (
            memory_repository.search_memories_hybrid
            if request.mode == "hybrid"
            else memory_repository.search_memories
        )
        arguments = {
            "query_vector": query_vector,
            **request.filters.model_dump(),
            **request.pagination.model_dump(),
        }
        if request.mode == "hybrid":
            arguments["query"] = request.query
        return search(session, **arguments)
    except SQLAlchemyError:
        raise database_unavailable() from None


@router.post("", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
def create_memory(
    memory_data: MemoryCreate,
    session: Annotated[Session, Depends(get_db_session)],
) -> Memory:
    """Create a Memory in one route-owned transaction."""

    try:
        if memory_data.project_id is not None and not memory_repository.project_exists(
            session, memory_data.project_id
        ):
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="project not found",
            )
        if (
            memory_data.supersedes_id is not None
            and memory_repository.get_memory(session, memory_data.supersedes_id) is None
        ):
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="superseded memory not found",
            )
        memory = memory_repository.create_memory(session, memory_data)
        session.commit()
        session.refresh(memory)
    except SQLAlchemyError:
        session.rollback()
        raise database_unavailable() from None
    return memory


@router.post(
    "/{memory_id}/embedding",
    response_model=MemoryEmbeddingRead,
    status_code=status.HTTP_200_OK,
)
def generate_memory_embedding(
    memory_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
    provider: Annotated[EmbeddingProvider, Depends(provider_dependency)],
) -> MemoryEmbeddingRead:
    """Explicitly create or idempotently update one Memory embedding."""

    try:
        memory = memory_repository.get_memory(session, memory_id)
        if memory is None:
            session.rollback()
            raise HTTPException(status_code=404, detail="memory not found")
        result = embedding_repository.generate_memory_embedding(
            session, memory, provider
        )
        session.commit()
    except InvalidEmbeddingResponseError:
        session.rollback()
        raise HTTPException(
            status_code=502, detail="invalid embedding response"
        ) from None
    except ProviderRequestError:
        session.rollback()
        raise HTTPException(
            status_code=502, detail="embedding provider failed"
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise database_unavailable() from None
    row = result.embedding
    return MemoryEmbeddingRead(
        id=row.id,
        memory_id=row.memory_id,
        provider=row.provider,
        model=row.model,
        dimensions=row.dimensions,
        input_hash=row.input_hash,
        embedded_at=row.embedded_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        generation_status=result.generation_status,
    )


@router.post(
    "/{memory_id}/sources",
    response_model=MemorySourceRead,
    status_code=status.HTTP_201_CREATED,
)
def link_source_to_memory(
    memory_id: uuid.UUID,
    link_data: MemorySourceLinkCreate,
    session: Annotated[Session, Depends(get_db_session)],
) -> MemorySource:
    """Link an existing Source to an existing Memory."""
    try:
        if memory_repository.get_memory(session, memory_id) is None:
            session.rollback()
            raise HTTPException(status_code=404, detail="memory not found")
        if source_repository.get_source(session, link_data.source_id) is None:
            session.rollback()
            raise HTTPException(status_code=404, detail="source not found")
        if source_repository.memory_source_link_exists(
            session, memory_id=memory_id, source_id=link_data.source_id
        ):
            session.rollback()
            raise HTTPException(
                status_code=409, detail="source already linked to memory"
            )
        link = source_repository.create_memory_source_link(
            session, memory_id=memory_id, link_data=link_data
        )
        session.commit()
        session.refresh(link)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="source already linked to memory"
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise database_unavailable() from None
    return link


@router.get("/{memory_id}/sources", response_model=list[LinkedSourceRead])
def list_sources_for_memory(
    memory_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[source_repository.LinkedSource]:
    """List a validated page of Sources linked to one Memory."""
    try:
        if memory_repository.get_memory(session, memory_id) is None:
            raise HTTPException(status_code=404, detail="memory not found")
        return source_repository.list_sources_for_memory(
            session, memory_id=memory_id, limit=limit, offset=offset
        )
    except SQLAlchemyError:
        raise database_unavailable() from None


@router.get("", response_model=list[MemoryRead])
def list_memories(
    session: Annotated[Session, Depends(get_db_session)],
    filters: Annotated[MemoryFilters, Query()],
) -> list[Memory]:
    """List a validated, deterministic page of Memories."""

    try:
        return memory_repository.list_memories(
            session,
            **filters.model_dump(),
        )
    except SQLAlchemyError:
        raise database_unavailable() from None


@router.get("/{memory_id}", response_model=MemoryRead)
def get_memory(
    memory_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> Memory:
    """Return one Memory by UUID."""

    try:
        memory = memory_repository.get_memory(session, memory_id)
    except SQLAlchemyError:
        raise database_unavailable() from None
    if memory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="memory not found",
        )
    return memory
