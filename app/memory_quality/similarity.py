"""Read-only duplicate and similarity detection policy."""

import re
import uuid
from dataclasses import dataclass
from math import isfinite
from typing import Literal

from sqlalchemy.orm import Session

from app.memory_quality.normalization import normalize_exact_content
from app.models.memory import Memory
from app.repositories import memories as memory_repository

Classification = Literal["exact_duplicate", "similar"]

LEXICAL_SIMILARITY_THRESHOLD = 0.60
SEMANTIC_SIMILARITY_THRESHOLD = 0.85
MINIMUM_SHARED_TOKENS = 3
MAX_CANDIDATE_LIMIT = 50
_SEARCH_POOL_LIMIT = 250
_MAX_QUERY_TOKENS = 100
_TOKEN = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class SimilarityCandidate:
    """One advisory classification supported by deterministic evidence."""

    memory: Memory
    classification: Classification
    lexical_similarity: float | None
    semantic_similarity: float | None
    reason: str


@dataclass(frozen=True)
class SimilarityCandidatePool:
    """Bounded retrieval evidence shared by read-only quality policies."""

    memories: dict[uuid.UUID, Memory]
    exact_ids: frozenset[uuid.UUID]
    semantic_scores: dict[uuid.UUID, float]


def _tokens(content: str) -> frozenset[str]:
    return frozenset(token.casefold() for token in _TOKEN.findall(content))


def _lexical_similarity(
    target_tokens: frozenset[str], candidate_content: str
) -> tuple[float, int]:
    candidate_tokens = _tokens(candidate_content)
    shared = len(target_tokens & candidate_tokens)
    union = len(target_tokens | candidate_tokens)
    return (shared / union if union else 0.0), shared


def _lexical_query(tokens: frozenset[str]) -> str | None:
    selected = sorted(tokens)[:_MAX_QUERY_TOKENS]
    if not selected:
        return None
    return " OR ".join(selected)


def _usable_vector(vector: list[float]) -> bool:
    return bool(vector) and all(isfinite(value) for value in vector) and any(vector)


def _candidate_sort_key(
    item: SimilarityCandidate,
) -> tuple[int, float, float, uuid.UUID]:
    return (
        0 if item.classification == "exact_duplicate" else 1,
        -(item.semantic_similarity if item.semantic_similarity is not None else -1.0),
        -(item.lexical_similarity if item.lexical_similarity is not None else -1.0),
        item.memory.id,
    )


def collect_similarity_candidate_pool(
    session: Session, *, target: Memory, exact_limit: int
) -> SimilarityCandidatePool:
    """Collect bounded same-scope candidates without classification or mutation."""
    normalized_target = normalize_exact_content(target.content)
    exact_rows = memory_repository.list_exact_duplicate_candidates(
        session,
        target=target,
        normalized_content=normalized_target,
        limit=exact_limit,
    )
    candidates: dict[uuid.UUID, Memory] = {row.id: row for row in exact_rows}
    exact_ids = set(candidates)

    target_tokens = _tokens(target.content)
    lexical_query = _lexical_query(target_tokens)
    if lexical_query is not None:
        for row in memory_repository.list_lexical_similarity_candidates(
            session,
            target=target,
            query=lexical_query,
            limit=_SEARCH_POOL_LIMIT,
        ):
            candidates[row.id] = row

    semantic_scores: dict[uuid.UUID, float] = {}
    target_embedding = memory_repository.get_memory_embedding(session, target.id)
    if target_embedding is not None and _usable_vector(target_embedding.embedding):
        for row, score in memory_repository.list_semantic_similarity_candidates(
            session,
            target=target,
            query_vector=target_embedding.embedding,
            provider=target_embedding.provider,
            model=target_embedding.model,
            dimensions=target_embedding.dimensions,
            limit=_SEARCH_POOL_LIMIT,
        ):
            if score is None or not isfinite(score):
                continue
            candidates[row.id] = row
            semantic_scores[row.id] = score

    return SimilarityCandidatePool(
        memories=candidates,
        exact_ids=frozenset(exact_ids),
        semantic_scores=semantic_scores,
    )


def detect_similar_memories(
    session: Session, *, target: Memory, limit: int
) -> list[SimilarityCandidate]:
    """Classify bounded same-project candidates without modifying persistence."""

    pool = collect_similarity_candidate_pool(session, target=target, exact_limit=limit)
    target_tokens = _tokens(target.content)

    results: list[SimilarityCandidate] = []
    for memory_id, memory in pool.memories.items():
        lexical_score, shared_tokens = _lexical_similarity(
            target_tokens, memory.content
        )
        semantic_score = pool.semantic_scores.get(memory_id)
        if memory_id in pool.exact_ids:
            results.append(
                SimilarityCandidate(
                    memory=memory,
                    classification="exact_duplicate",
                    lexical_similarity=lexical_score,
                    semantic_similarity=semantic_score,
                    reason=(
                        "content matches after surrounding/repeated whitespace "
                        "normalization"
                    ),
                )
            )
            continue
        lexical_match = (
            shared_tokens >= MINIMUM_SHARED_TOKENS
            and lexical_score >= LEXICAL_SIMILARITY_THRESHOLD
        )
        semantic_match = (
            semantic_score is not None
            and semantic_score >= SEMANTIC_SIMILARITY_THRESHOLD
        )
        if not lexical_match and not semantic_match:
            continue
        evidence = []
        if lexical_match:
            evidence.append(
                f"lexical token Jaccard {lexical_score:.3f} with "
                f"{shared_tokens} shared tokens"
            )
        if semantic_match:
            evidence.append(f"stored-embedding cosine similarity {semantic_score:.3f}")
        results.append(
            SimilarityCandidate(
                memory=memory,
                classification="similar",
                lexical_similarity=lexical_score,
                semantic_similarity=semantic_score,
                reason="; ".join(evidence),
            )
        )

    results.sort(key=_candidate_sort_key)
    return results[:limit]
