"""Typed models for the retrieval evaluation dataset and report."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SearchMode = Literal["lexical", "semantic", "hybrid"]


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    query: str = Field(min_length=1, max_length=500)
    project_scope: str | None = None
    relevant: list[str]
    irrelevant: list[str] = Field(default_factory=list)
    modes: list[SearchMode] = Field(min_length=1)
    limit: int = Field(ge=1, le=100)

    @model_validator(mode="after")
    def validate_keys(self) -> "EvaluationCase":
        if len(set(self.relevant)) != len(self.relevant):
            raise ValueError("relevant fixture keys must be unique")
        if set(self.relevant) & set(self.irrelevant):
            raise ValueError("relevant and irrelevant fixture keys must be disjoint")
        if len(set(self.modes)) != len(self.modes):
            raise ValueError("search modes must be unique")
        return self


class EvaluationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(pattern=r"^[1-9][0-9]*\.[0-9]+$")
    cases: list[EvaluationCase] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_case_ids(self) -> "EvaluationDataset":
        ids = [case.case_id for case in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("case IDs must be unique")
        return self


class CaseMetrics(BaseModel):
    hit_at_k: float
    recall_at_k: float | None
    reciprocal_rank: float | None
    precision_at_k: float
    no_expected_match: bool | None


class CaseResult(BaseModel):
    case_id: str
    mode: SearchMode
    limit: int
    expected_keys: list[str]
    retrieved_keys: list[str]
    metrics: CaseMetrics


class AggregateMetrics(BaseModel):
    case_count: int
    hit_at_k: float
    recall_at_k: float | None
    mean_reciprocal_rank: float | None
    precision_at_k: float
    no_relevant_case_accuracy: float | None


class ModeResult(BaseModel):
    mode: SearchMode
    metrics: AggregateMetrics
    threshold_passed: bool | None = None


class EvaluationReport(BaseModel):
    dataset_version: str
    case_count: int
    case_results: list[CaseResult]
    modes: list[ModeResult]
    baseline_passed: bool | None = None
