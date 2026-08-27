"""Configured provider dependency for Project Watch v1."""

from app.core.config import get_settings
from app.project_watch.openai_provider import OpenAIProjectWatchProvider
from app.project_watch.provider import (
    ProjectWatchProvider,
    ProjectWatchProviderUnavailableError,
)


def get_project_watch_provider() -> ProjectWatchProvider:
    settings = get_settings()
    if (
        settings.openai_api_key is None
        or not settings.openai_api_key.get_secret_value().strip()
    ):
        raise ProjectWatchProviderUnavailableError
    return OpenAIProjectWatchProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.answer_model,
        max_output_tokens=settings.answer_max_output_tokens,
    )
