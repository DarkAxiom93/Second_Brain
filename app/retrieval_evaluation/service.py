"""Pure metrics and orchestration over the production retrieval function."""

import uuid
from collections.abc import Callable

from app.repositories.memories import ScoredMemory
from app.retrieval_evaluation.models import (
    AggregateMetrics,
    CaseMetrics,
    CaseResult,
    EvaluationDataset,
    EvaluationReport,
    ModeResult,
    SearchMode,
)

Retriever = Callable[[str, SearchMode, uuid.UUID | None, int], list[ScoredMemory]]


def calculate_metrics(expected: set[str], retrieved: list[str]) -> CaseMetrics:
    """Calculate transparent rank metrics for one bounded result list."""

    matched = [key for key in retrieved if key in expected]
    hit = float(bool(matched))
    precision = len(matched) / len(retrieved) if retrieved else 0.0
    if not expected:
        return CaseMetrics(
            hit_at_k=0.0,
            recall_at_k=None,
            reciprocal_rank=None,
            precision_at_k=precision,
            no_expected_match=not retrieved,
        )
    first_rank = next(
        (rank for rank, key in enumerate(retrieved, start=1) if key in expected), None
    )
    return CaseMetrics(
        hit_at_k=hit,
        recall_at_k=len(set(matched)) / len(expected),
        reciprocal_rank=(1.0 / first_rank) if first_rank is not None else 0.0,
        precision_at_k=precision,
        no_expected_match=None,
    )


def _average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def aggregate(case_results: list[CaseResult], mode: SearchMode) -> ModeResult:
    selected = [result for result in case_results if result.mode == mode]
    relevant = [result.metrics for result in selected if result.expected_keys]
    empty = [result.metrics for result in selected if not result.expected_keys]
    return ModeResult(
        mode=mode,
        metrics=AggregateMetrics(
            case_count=len(selected),
            hit_at_k=sum(item.hit_at_k for item in relevant) / len(relevant),
            recall_at_k=_average(
                [item.recall_at_k for item in relevant if item.recall_at_k is not None]
            ),
            mean_reciprocal_rank=_average(
                [
                    item.reciprocal_rank
                    for item in relevant
                    if item.reciprocal_rank is not None
                ]
            ),
            precision_at_k=sum(item.metrics.precision_at_k for item in selected)
            / len(selected),
            no_relevant_case_accuracy=_average(
                [float(item.no_expected_match is True) for item in empty]
            ),
        ),
    )


def apply_thresholds(
    report: EvaluationReport, thresholds: dict[SearchMode, dict[str, float]]
) -> EvaluationReport:
    passed = True
    for mode in report.modes:
        required = thresholds.get(mode.mode, {})
        actual = mode.metrics.model_dump()
        mode.threshold_passed = all(
            actual[name] is not None and actual[name] >= minimum
            for name, minimum in required.items()
        )
        passed = passed and mode.threshold_passed
    report.baseline_passed = passed
    return report


def evaluate_dataset(
    dataset: EvaluationDataset,
    *,
    fixture_ids: dict[str, uuid.UUID],
    project_ids: dict[str, uuid.UUID],
    retrieve: Retriever,
) -> EvaluationReport:
    """Resolve fixture keys and evaluate each case/mode in stable order."""

    reverse = {memory_id: key for key, memory_id in fixture_ids.items()}
    results: list[CaseResult] = []
    for case in sorted(dataset.cases, key=lambda item: item.case_id):
        unknown = (set(case.relevant) | set(case.irrelevant)) - fixture_ids.keys()
        if unknown:
            raise ValueError(f"unknown fixture keys: {', '.join(sorted(unknown))}")
        if case.project_scope is not None and case.project_scope not in project_ids:
            raise ValueError(f"unknown project scope: {case.project_scope}")
        project_id = project_ids.get(case.project_scope) if case.project_scope else None
        for mode in sorted(case.modes):
            rows = retrieve(case.query, mode, project_id, case.limit)
            keys = [reverse[row.memory.id] for row in rows if row.memory.id in reverse]
            results.append(
                CaseResult(
                    case_id=case.case_id,
                    mode=mode,
                    limit=case.limit,
                    expected_keys=case.relevant,
                    retrieved_keys=keys,
                    metrics=calculate_metrics(set(case.relevant), keys),
                )
            )
    ordered_modes: tuple[SearchMode, ...] = ("lexical", "semantic", "hybrid")
    modes = [
        aggregate(results, mode)
        for mode in ordered_modes
        if any(result.mode == mode for result in results)
    ]
    return EvaluationReport(
        dataset_version=dataset.version,
        case_count=len(dataset.cases),
        case_results=results,
        modes=modes,
    )
