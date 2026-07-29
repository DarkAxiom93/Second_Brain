"""Narrow embedding provider abstractions."""

from app.embeddings.dependencies import get_embedding_provider
from app.embeddings.provider import (
    EmbeddingProvider,
    InvalidEmbeddingResponseError,
    ProviderRequestError,
    ProviderUnavailableError,
)

__all__ = [
    "EmbeddingProvider",
    "InvalidEmbeddingResponseError",
    "ProviderRequestError",
    "ProviderUnavailableError",
    "get_embedding_provider",
]
