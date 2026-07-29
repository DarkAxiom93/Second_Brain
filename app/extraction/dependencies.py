"""Lazy extraction-provider dependency."""

from app.core.config import get_settings
from app.extraction.openai_provider import OpenAIExtractionProvider
from app.extraction.provider import ExtractionProvider


def get_extraction_provider() -> ExtractionProvider | None:
    settings = get_settings()
    if (
        settings.openai_api_key is None
        or not settings.openai_api_key.get_secret_value().strip()
    ):
        return None
    return OpenAIExtractionProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.extraction_model,
        prompt_version=settings.extraction_prompt_version,
        timeout_seconds=settings.extraction_timeout_seconds,
        max_output_tokens=settings.extraction_max_output_tokens,
    )
