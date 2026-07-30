"""Unit coverage for deterministic retrieval evaluation metrics and validation."""

import uuid

import pytest
from pydantic import ValidationError

from app.models.memory import Memory
from app.repositories.memories import ScoredMemory
from app.retrieval_evaluation.models import EvaluationDataset
from app.retrieval_evaluation.service import (
    apply_thresholds,
    calculate_metrics,
    evaluate_dataset,
)


def test_metric_formulas_cover_multiple_and_missing_relevant_results() -> None:
    metrics = calculate_metrics({"a", "b", "missing"}, ["x", "a", "b"])
    assert metrics.hit_at_k == 1.0
    assert metrics.recall_at_k == pytest.approx(2 / 3)
    assert metrics.reciprocal_rank == 0.5
    assert metrics.precision_at_k == pytest.approx(2 / 3)


def test_no_relevant_case_has_explicit_not_applicable_metrics() -> None:
    empty = calculate_metrics(set(), [])
    distractor = calculate_metrics(set(), ["distractor"])
    assert empty.recall_at_k is None
    assert empty.reciprocal_rank is None
    assert empty.no_expected_match is True
    assert distractor.no_expected_match is False


def test_evaluation_order_aggregation_and_threshold_outcomes_are_stable() -> None:
    first_id, second_id = uuid.uuid4(), uuid.uuid4()
    dataset = EvaluationDataset.model_validate(
        {
            "version": "1.0",
            "cases": [
                {
                    "case_id": "z_case",
                    "query": "q",
                    "relevant": ["first"],
                    "modes": ["hybrid", "lexical"],
                    "limit": 2,
                },
                {
                    "case_id": "a_case",
                    "query": "q",
                    "relevant": ["second"],
                    "modes": ["lexical"],
                    "limit": 2,
                },
            ],
        }
    )

    def retrieve(*_args: object) -> list[ScoredMemory]:
        return [ScoredMemory(Memory(id=first_id, content="first"), None, None)]

    report = evaluate_dataset(
        dataset,
        fixture_ids={"first": first_id, "second": second_id},
        project_ids={},
        retrieve=retrieve,
    )
    assert [(row.case_id, row.mode) for row in report.case_results] == [
        ("a_case", "lexical"),
        ("z_case", "hybrid"),
        ("z_case", "lexical"),
    ]
    lexical = next(mode for mode in report.modes if mode.mode == "lexical")
    assert lexical.metrics.hit_at_k == 0.5
    apply_thresholds(report, {"lexical": {"hit_at_k": 0.5}})
    assert lexical.threshold_passed is True
    apply_thresholds(report, {"lexical": {"hit_at_k": 0.6}})
    assert lexical.threshold_passed is False
    assert report.baseline_passed is False


@pytest.mark.parametrize(
    "payload",
    [
        {"version": "bad", "cases": []},
        {
            "version": "1.0",
            "cases": [
                {
                    "case_id": "duplicate",
                    "query": "q",
                    "relevant": ["x", "x"],
                    "modes": ["lexical"],
                    "limit": 1,
                }
            ],
        },
    ],
)
def test_invalid_evaluation_dataset_is_rejected(payload: object) -> None:
    with pytest.raises(ValidationError):
        EvaluationDataset.model_validate(payload)
