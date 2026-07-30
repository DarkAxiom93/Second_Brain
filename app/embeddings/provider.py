"""Typed contract and safe errors for one embedding provider."""

from typing import Protocol


class ProviderUnavailableError(Exception):
    """Raised when configured provider credentials are unavailable."""


class ProviderRequestError(Exception):
    """Raised when the external provider request fails."""


class InvalidEmbeddingResponseError(Exception):
    """Raised when a provider returns a malformed embedding."""


class EmbeddingProvider(Protocol):
    """Small synchronous embedding-provider contract."""

    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...

    def embed_many(self, texts: list[str]) -> list[list[float]]: ...
