"""Typed answer-provider boundary."""

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, model_validator


class AnswerProviderResult(BaseModel):
    """Strict, bounded provider output."""

    model_config = ConfigDict(extra="forbid")

    answer_status: Literal["answered", "insufficient_evidence"]
    answer: str
    citation_labels: list[str]

    @model_validator(mode="after")
    def validate_status_contract(self) -> "AnswerProviderResult":
        self.answer = self.answer.strip()
        if not self.answer or len(self.answer) > 4000:
            raise ValueError("answer must be nonblank and at most 4000 characters")
        if self.answer_status == "answered" and not self.citation_labels:
            raise ValueError("answered result requires citations")
        if self.answer_status == "insufficient_evidence" and self.citation_labels:
            raise ValueError("insufficient evidence cannot have citations")
        return self


class AnswerProvider(Protocol):
    def answer(self, *, query: str, evidence_context: str) -> AnswerProviderResult: ...


class ProviderUnavailableError(Exception):
    pass


class ProviderRequestError(Exception):
    pass


class InvalidAnswerResponseError(Exception):
    pass
