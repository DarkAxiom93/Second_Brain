"""Strict bounded Curator synthesis contract."""

from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

EvidenceId = Annotated[str, StringConstraints(pattern=r"^e[1-9][0-9]{0,2}$")]
SafeText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class CuratorFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    text: SafeText
    evidence: Annotated[list[EvidenceId], Field(min_length=1, max_length=20)]


class CuratorProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    action_type: Literal["memory.update"]
    target_evidence: EvidenceId
    proposed_input: dict[str, object]
    evidence: Annotated[list[EvidenceId], Field(min_length=1, max_length=20)]


class CuratorProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    findings: Annotated[list[CuratorFinding], Field(max_length=10)]
    proposals: Annotated[list[CuratorProposal], Field(max_length=5)]


class CuratorProvider(Protocol):
    def synthesize(
        self, *, goal: str, evidence: list[dict[str, object]]
    ) -> CuratorProviderResult: ...


class FakeCuratorProvider:
    def __init__(self, result: CuratorProviderResult | Exception) -> None:
        self.result, self.calls = result, 0

    def synthesize(
        self, *, goal: str, evidence: list[dict[str, object]]
    ) -> CuratorProviderResult:
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class CuratorProviderError(Exception):
    pass


class CuratorProviderUnavailableError(CuratorProviderError):
    pass


class CuratorProviderTimeoutError(CuratorProviderError):
    pass


class CuratorProviderRequestError(CuratorProviderError):
    pass


class CuratorOutputInvalidError(CuratorProviderError):
    pass
