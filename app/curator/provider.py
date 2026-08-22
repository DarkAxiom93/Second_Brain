"""Strict bounded Curator synthesis contract."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.memory import MemoryStatus, MemoryType, MemoryUpdate

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


class ProviderMemoryUpdate(BaseModel):
    """Closed full value envelope translated to the selected partial update."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    content: Annotated[str | None, StringConstraints(min_length=1, max_length=16000)]
    source: Annotated[str | None, StringConstraints(min_length=1, max_length=100)]
    title: Annotated[str | None, StringConstraints(max_length=255)]
    summary: Annotated[str | None, StringConstraints(max_length=4000)]
    memory_type: MemoryType | None
    importance: Annotated[float | None, Field(ge=0.0, le=1.0)]
    confidence: Annotated[float | None, Field(ge=0.0, le=1.0)]
    status: MemoryStatus | None
    event_time: datetime | None
    expires_at: datetime | None
    supersedes_id: uuid.UUID | None


class StrictCuratorProposal(BaseModel):
    """Provider-only closed representation of one partial Memory update."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    action_type: Literal["memory.update"]
    target_evidence: EvidenceId
    updated_fields: Annotated[
        list[
            Literal[
                "content",
                "source",
                "title",
                "summary",
                "memory_type",
                "importance",
                "confidence",
                "status",
                "event_time",
                "expires_at",
                "supersedes_id",
            ]
        ],
        Field(min_length=1, max_length=11),
    ]
    proposed_input: ProviderMemoryUpdate
    evidence: Annotated[list[EvidenceId], Field(min_length=1, max_length=20)]


class StrictCuratorProviderResult(BaseModel):
    """Provider-only DTO with a recursively closed proposal input."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    findings: Annotated[list[CuratorFinding], Field(max_length=10)]
    proposals: Annotated[list[StrictCuratorProposal], Field(max_length=5)]


def translate_curator_result(value: Any) -> CuratorProviderResult:
    provider_result = StrictCuratorProviderResult.model_validate(value, strict=True)
    proposals: list[dict[str, object]] = []
    for proposal in provider_result.proposals:
        if len(proposal.updated_fields) != len(set(proposal.updated_fields)):
            raise ValueError("duplicate updated field")
        complete = proposal.proposed_input.model_dump(mode="python")
        selected: dict[str, Any] = {
            field: complete[field] for field in proposal.updated_fields
        }
        selected = MemoryUpdate.model_validate(selected).model_dump(
            mode="python", exclude_unset=True
        )
        proposals.append(
            {
                "action_type": proposal.action_type,
                "target_evidence": proposal.target_evidence,
                "proposed_input": selected,
                "evidence": proposal.evidence,
            }
        )
    return CuratorProviderResult.model_validate(
        {"findings": provider_result.findings, "proposals": proposals}, strict=True
    )


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
