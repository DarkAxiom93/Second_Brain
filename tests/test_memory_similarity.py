"""Unit coverage for deterministic Memory similarity policy helpers."""

import uuid

from app.memory_quality.normalization import normalize_exact_content
from app.memory_quality.similarity import (
    LEXICAL_SIMILARITY_THRESHOLD,
    MINIMUM_SHARED_TOKENS,
    SimilarityCandidate,
    _candidate_sort_key,
)
from app.models.memory import Memory


def test_exact_normalization_only_collapses_whitespace() -> None:
    variants = (
        "Alpha  beta",
        "Alpha\tbeta",
        "Alpha\nbeta",
        " \t\nAlpha \t\n beta\r\f\v ",
    )
    assert {normalize_exact_content(value) for value in variants} == {"Alpha beta"}
    assert normalize_exact_content("Alpha beta") != normalize_exact_content(
        "alpha beta"
    )
    assert normalize_exact_content("Alpha, beta") != normalize_exact_content(
        "Alpha beta"
    )
    assert normalize_exact_content("Alpha\u00a0beta") == "Alpha\u00a0beta"
    assert normalize_exact_content("Alpha\u00a0beta") != "Alpha beta"


def test_similarity_policy_constants_are_conservative_and_stable() -> None:
    assert LEXICAL_SIMILARITY_THRESHOLD == 0.60
    assert MINIMUM_SHARED_TOKENS == 3


def test_all_nullable_score_combinations_have_stable_ordering() -> None:
    def candidate(
        identifier: int,
        classification: str,
        lexical: float | None,
        semantic: float | None,
    ) -> SimilarityCandidate:
        return SimilarityCandidate(
            memory=Memory(id=uuid.UUID(int=identifier), content="candidate"),
            classification=classification,  # type: ignore[arg-type]
            lexical_similarity=lexical,
            semantic_similarity=semantic,
            reason="test",
        )

    rows = [
        candidate(9, "similar", None, None),
        candidate(8, "similar", 0.8, 0.8),
        candidate(7, "similar", 0.8, 0.8),
        candidate(6, "exact_duplicate", 1.0, None),
        candidate(5, "similar", 0.7, 0.9),
        candidate(4, "similar", None, 0.9),
        candidate(3, "similar", 0.9, None),
    ]
    assert [row.memory.id.int for row in sorted(rows, key=_candidate_sort_key)] == [
        6,
        5,
        4,
        7,
        8,
        3,
        9,
    ]
