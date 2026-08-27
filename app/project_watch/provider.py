"""Closed Project Watch synthesis contract."""

from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class ProjectWatchClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    evidence_ids: Annotated[list[str], Field(min_length=1, max_length=20)]


class ProjectWatchProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["changes_found", "no_meaningful_change"]
    findings: Annotated[list[ProjectWatchClaim], Field(max_length=5)]


class ProjectWatchProvider(Protocol):
    def synthesize(
        self, *, goal: str, evidence: list[dict[str, object]]
    ) -> ProjectWatchProviderResult: ...


class ProjectWatchProviderError(Exception):
    pass


class ProjectWatchProviderUnavailableError(ProjectWatchProviderError):
    pass


class ProjectWatchProviderTimeoutError(ProjectWatchProviderError):
    pass


class ProjectWatchProviderRequestError(ProjectWatchProviderError):
    pass


class ProjectWatchOutputInvalidError(ProjectWatchProviderError):
    pass
