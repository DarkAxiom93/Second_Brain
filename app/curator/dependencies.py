from app.core.config import get_settings
from app.curator.openai_provider import OpenAICuratorProvider
from app.curator.provider import CuratorProvider, CuratorProviderUnavailableError


def get_curator_provider() -> CuratorProvider:
    settings = get_settings()
    if (
        settings.openai_api_key is None
        or not settings.openai_api_key.get_secret_value().strip()
    ):
        raise CuratorProviderUnavailableError
    return OpenAICuratorProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.answer_model,
        max_output_tokens=settings.answer_max_output_tokens,
    )
