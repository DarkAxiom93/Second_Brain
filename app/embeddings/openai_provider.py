"""Official OpenAI SDK implementation of the embedding contract."""

import math
from numbers import Real

from openai import OpenAI

from app.embeddings.provider import (
    InvalidEmbeddingResponseError,
    ProviderRequestError,
)


def validate_embedding(vector: object, dimensions: int) -> list[float]:
    """Return a finite float vector with exactly the configured dimensions."""

    if not isinstance(vector, list) or len(vector) != dimensions:
        raise InvalidEmbeddingResponseError
    validated: list[float] = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise InvalidEmbeddingResponseError
        number = float(value)
        if not math.isfinite(number):
            raise InvalidEmbeddingResponseError
        validated.append(number)
    return validated


class OpenAIEmbeddingProvider:
    """Generate one embedding through the synchronous official client."""

    def __init__(
        self, *, api_key: str, model: str, dimensions: int, timeout_seconds: float
    ) -> None:
        self._model = model
        self._dimensions = dimensions
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        try:
            response = self._client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions,
                encoding_format="float",
            )
        except Exception as exc:
            raise ProviderRequestError from exc
        if len(response.data) != 1:
            raise InvalidEmbeddingResponseError
        return validate_embedding(response.data[0].embedding, self.dimensions)
