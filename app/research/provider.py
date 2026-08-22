"""Bounded Research synthesis provider contract."""

from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ClaimText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
EvidenceId = Annotated[str, StringConstraints(pattern=r"^e[1-9][0-9]{0,2}$")]


class ResearchClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    text: ClaimText
    citations: Annotated[list[EvidenceId], Field(min_length=1, max_length=20)]


class ResearchProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    status: Literal["answered", "insufficient_evidence"]
    claims: Annotated[list[ResearchClaim], Field(max_length=5)]
    insufficiency: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
    ] = None

    @model_validator(mode="after")
    def consistent_status(self) -> "ResearchProviderResult":
        if self.status == "answered" and (
            not self.claims or self.insufficiency is not None
        ):
            raise ValueError("answered research requires claims only")
        if self.status == "insufficient_evidence" and (
            self.claims or self.insufficiency is None
        ):
            raise ValueError("insufficient research requires explanation only")
        return self


class StrictResearchProviderResult(BaseModel):
    """Provider-only DTO with every strict-schema property required."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    status: Literal["answered", "insufficient_evidence"]
    claims: Annotated[list[ResearchClaim], Field(max_length=5)]
    insufficiency: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
    ]


class ResearchProvider(Protocol):
    def synthesize(
        self, *, goal: str, evidence: list[dict[str, object]]
    ) -> ResearchProviderResult: ...


class FakeResearchProvider:
    def __init__(self, result: ResearchProviderResult | Exception) -> None:
        self.result = result
        self.calls = 0

    def synthesize(
        self, *, goal: str, evidence: list[dict[str, object]]
    ) -> ResearchProviderResult:
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class ResearchProviderError(Exception):
    pass


class ResearchProviderUnavailableError(ResearchProviderError):
    pass


class ResearchProviderTimeoutError(ResearchProviderError):
    pass


class ResearchProviderRequestError(ResearchProviderError):
    pass


class ResearchOutputInvalidError(ResearchProviderError):
    pass
