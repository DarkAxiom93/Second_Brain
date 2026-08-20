"""Application-owned Research provider resolution."""

from app.core.config import get_settings
from app.research.openai_provider import OpenAIResearchProvider
from app.research.provider import ResearchProvider, ResearchProviderUnavailableError


def get_research_provider() -> ResearchProvider:
    settings = get_settings()
    if (
        settings.openai_api_key is None
        or not settings.openai_api_key.get_secret_value().strip()
    ):
        raise ResearchProviderUnavailableError
    return OpenAIResearchProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.answer_model,
        max_output_tokens=settings.answer_max_output_tokens,
    )
