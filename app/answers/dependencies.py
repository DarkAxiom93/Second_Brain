"""Answer-provider dependency wiring."""

from app.answers.openai_provider import OpenAIAnswerProvider
from app.answers.provider import AnswerProvider, ProviderUnavailableError
from app.core.config import get_settings


def get_answer_provider() -> AnswerProvider:
    settings = get_settings()
    if settings.openai_api_key is None:
        raise ProviderUnavailableError
    return OpenAIAnswerProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.answer_model,
        timeout_seconds=settings.answer_timeout_seconds,
        max_output_tokens=settings.answer_max_output_tokens,
    )
