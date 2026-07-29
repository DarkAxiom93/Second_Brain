"""FastAPI dependency construction for the configured embedding provider."""

from app.core.config import get_settings
from app.embeddings.openai_provider import OpenAIEmbeddingProvider
from app.embeddings.provider import EmbeddingProvider, ProviderUnavailableError


def get_embedding_provider() -> EmbeddingProvider:
    """Build the configured provider only when an explicit action requests it."""

    settings = get_settings()
    if (
        settings.openai_api_key is None
        or not settings.openai_api_key.get_secret_value().strip()
    ):
        raise ProviderUnavailableError
    return OpenAIEmbeddingProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
