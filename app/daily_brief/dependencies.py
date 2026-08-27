"""Application-owned Daily Brief provider resolution."""

from app.core.config import get_settings
from app.daily_brief.openai_provider import OpenAIDailyBriefProvider
from app.daily_brief.provider import (
    DailyBriefProvider,
    DailyBriefProviderUnavailableError,
)


def get_daily_brief_provider() -> DailyBriefProvider:
    settings = get_settings()
    if (
        settings.openai_api_key is None
        or not settings.openai_api_key.get_secret_value().strip()
    ):
        raise DailyBriefProviderUnavailableError
    return OpenAIDailyBriefProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.answer_model,
        max_output_tokens=settings.answer_max_output_tokens,
    )
