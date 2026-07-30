"""Conservative English-only explicit-polarity contradiction policy."""

import re
import uuid
from dataclasses import dataclass
from typing import Literal, cast

from sqlalchemy.orm import Session

from app.memory_quality.normalization import normalize_exact_content
from app.memory_quality.similarity import (
    _lexical_similarity,
    _tokens,
    collect_similarity_candidate_pool,
)
from app.models.memory import Memory

EvidenceType = Literal["explicit_negation", "opposing_boolean_state"]
Classification = Literal["potential_contradiction"]

_SURROUNDING_PUNCTUATION = ".,;:!?()[]{}\"'"
_ASCII_WHITESPACE = re.compile(r"[ \t\n\r\f\v]+")
_NEGATION_PAIRS = (
    (("is",), ("is", "not")),
    (("are",), ("are", "not")),
    (("was",), ("was", "not")),
    (("were",), ("were", "not")),
    (("can",), ("cannot",)),
    (("can",), ("can", "not")),
)
_BOOLEAN_PAIRS = (
    (("enabled",), ("disabled",)),
    (("active",), ("inactive",)),
    (("true",), ("false",)),
    (("on",), ("off",)),
    (("available",), ("unavailable",)),
)
_EVIDENCE_PRECEDENCE: dict[EvidenceType, int] = {
    "explicit_negation": 0,
    "opposing_boolean_state": 1,
}


@dataclass(frozen=True)
class OpposingStates:
    """Deterministic opposing markers found at one identical anchor position."""

    evidence_type: EvidenceType
    target_state: str
    candidate_state: str


@dataclass(frozen=True)
class ContradictionCandidate:
    """One advisory potential contradiction with deterministic evidence."""

    memory: Memory
    classification: Classification
    evidence_type: EvidenceType
    reason: str
    lexical_similarity: float | None
    semantic_similarity: float | None
    target_state: str
    candidate_state: str


def _normalized_tokens(content: str) -> tuple[str, ...]:
    return tuple(
        token.strip(_SURROUNDING_PUNCTUATION).casefold()
        for token in _ASCII_WHITESPACE.split(content)
        if token.strip(_SURROUNDING_PUNCTUATION)
    )


def _anchor_without(
    tokens: tuple[str, ...], position: int, marker: tuple[str, ...]
) -> tuple[str, ...] | None:
    if tokens[position : position + len(marker)] != marker:
        return None
    return tokens[:position] + tokens[position + len(marker) :]


def detect_opposing_states(
    target_content: str, candidate_content: str
) -> OpposingStates | None:
    """Return a supported opposing marker only for an exactly equal anchor."""

    target = _normalized_tokens(target_content)
    candidate = _normalized_tokens(candidate_content)
    for evidence_type, pairs in (
        ("explicit_negation", _NEGATION_PAIRS),
        ("opposing_boolean_state", _BOOLEAN_PAIRS),
    ):
        for left, right in pairs:
            for target_marker, candidate_marker in ((left, right), (right, left)):
                for position in range(len(target)):
                    target_anchor = _anchor_without(target, position, target_marker)
                    candidate_anchor = _anchor_without(
                        candidate, position, candidate_marker
                    )
                    if (
                        target_anchor is not None
                        and candidate_anchor is not None
                        and target_anchor == candidate_anchor
                    ):
                        return OpposingStates(
                            evidence_type=cast(EvidenceType, evidence_type),
                            target_state=" ".join(target_marker),
                            candidate_state=" ".join(candidate_marker),
                        )
    return None


def _sort_key(
    item: ContradictionCandidate,
) -> tuple[int, float, float, uuid.UUID]:
    return (
        _EVIDENCE_PRECEDENCE[item.evidence_type],
        -(item.semantic_similarity if item.semantic_similarity is not None else -1.0),
        -(item.lexical_similarity if item.lexical_similarity is not None else -1.0),
        item.memory.id,
    )


def detect_memory_contradictions(
    session: Session, *, target: Memory, limit: int
) -> list[ContradictionCandidate]:
    """Evaluate a bounded similarity pool for explicit polarity only."""

    pool = collect_similarity_candidate_pool(session, target=target, exact_limit=limit)
    target_tokens = _tokens(target.content)
    normalized_target = normalize_exact_content(target.content)
    results: list[ContradictionCandidate] = []
    for memory_id, memory in pool.memories.items():
        if normalize_exact_content(memory.content) == normalized_target:
            continue
        if (
            target.event_time is not None
            and memory.event_time is not None
            and target.event_time != memory.event_time
        ):
            continue
        opposing = detect_opposing_states(target.content, memory.content)
        if opposing is None:
            continue
        lexical_score, _ = _lexical_similarity(target_tokens, memory.content)
        results.append(
            ContradictionCandidate(
                memory=memory,
                classification="potential_contradiction",
                evidence_type=opposing.evidence_type,
                reason=(
                    "supported opposing states occur at the same position and "
                    "the remaining normalized proposition anchor is exactly equal"
                ),
                lexical_similarity=lexical_score,
                semantic_similarity=pool.semantic_scores.get(memory_id),
                target_state=opposing.target_state,
                candidate_state=opposing.candidate_state,
            )
        )
    results.sort(key=_sort_key)
    return results[:limit]
