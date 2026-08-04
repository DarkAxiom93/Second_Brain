"""Application-owned resolution of the configured planning provider."""

from app.agent_planning.openai_provider import OpenAIPlanningProvider
from app.agent_planning.provider import (
    PlanningProvider,
    PlanningProviderUnavailableError,
)
from app.core.config import get_settings


def get_planning_provider() -> PlanningProvider:
    settings = get_settings()
    if settings.openai_api_key is None:
        raise PlanningProviderUnavailableError
    api_key = settings.openai_api_key.get_secret_value()
    if not api_key.strip():
        raise PlanningProviderUnavailableError
    return OpenAIPlanningProvider(
        api_key=api_key,
        model=settings.answer_model,
        max_output_tokens=settings.answer_max_output_tokens,
    )


def configured_embedding_provider_available() -> bool:
    settings = get_settings()
    return bool(
        settings.openai_api_key is not None
        and settings.openai_api_key.get_secret_value().strip()
    )
