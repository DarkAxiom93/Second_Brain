"""Closed Daily Brief synthesis provider contract."""

from typing import Protocol

from app.research.provider import ResearchProviderResult

DailyBriefProviderResult = ResearchProviderResult


class DailyBriefProvider(Protocol):
    def synthesize(
        self, *, goal: str, evidence: list[dict[str, object]]
    ) -> DailyBriefProviderResult: ...


class DailyBriefProviderError(Exception):
    pass


class DailyBriefProviderUnavailableError(DailyBriefProviderError):
    pass


class DailyBriefProviderTimeoutError(DailyBriefProviderError):
    pass


class DailyBriefProviderRequestError(DailyBriefProviderError):
    pass


class DailyBriefOutputInvalidError(DailyBriefProviderError):
    pass
