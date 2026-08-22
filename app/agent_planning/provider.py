"""Typed, bounded Planning Provider contract and safe failures."""

from typing import Annotated, Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

BoundedText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]
EvidenceText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class PlanningProviderUnavailableError(Exception):
    pass


class PlanningProviderTimeoutError(Exception):
    pass


class PlanningProviderRequestError(Exception):
    pass


class PlanningOutputInvalidError(Exception):
    pass


class ProposedPlanningStep(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    purpose: BoundedText
    tool_name: Annotated[
        str, StringConstraints(min_length=1, max_length=200, pattern=r"^[a-z0-9._]+$")
    ]
    tool_version: Annotated[int, Field(gt=0)]
    candidate_input: dict[str, Any]
    expected_evidence: Annotated[list[EvidenceText], Field(min_length=1, max_length=10)]
    success_condition: BoundedText
    stop_condition: BoundedText


class PlanningResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    goal_summary: Annotated[
        str, StringConstraints(strip_whitespace=False, min_length=1, max_length=1000)
    ]
    steps: Annotated[list[ProposedPlanningStep], Field(min_length=1, max_length=12)]


class ProviderPlanningStep(BaseModel):
    """Strict-schema-safe provider representation of one proposed step."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    purpose: BoundedText
    tool_name: Annotated[
        str, StringConstraints(min_length=1, max_length=200, pattern=r"^[a-z0-9._]+$")
    ]
    tool_version: Annotated[int, Field(gt=0)]
    candidate_input: dict[str, Any]
    expected_evidence: Annotated[list[EvidenceText], Field(min_length=1, max_length=10)]
    success_condition: BoundedText
    stop_condition: BoundedText


class ProviderPlanningResult(BaseModel):
    """Provider-facing plan constrained by a registry-derived submitted schema."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    steps: Annotated[list[ProviderPlanningStep], Field(min_length=1, max_length=12)]


class PlanningContext(BaseModel):
    """Application-owned allowlist sent to the provider."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    goal_summary: str
    scope: dict[str, str]
    registry_version: str
    policy_version: str
    budgets: dict[str, int]
    permitted_tools: list[dict[str, Any]]
    output_contract: dict[str, Any]


class PlanningProvider(Protocol):
    def plan(self, context: PlanningContext) -> PlanningResult: ...


class FakePlanningProvider:
    """Deterministic no-network provider for tests."""

    def __init__(self, result: PlanningResult | Exception) -> None:
        self._result = result
        self.calls = 0

    def plan(self, context: PlanningContext) -> PlanningResult:
        self.calls += 1
        if isinstance(self._result, Exception):
            raise self._result
        return self._result
