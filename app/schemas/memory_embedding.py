"""Public metadata response for explicit embedding generation."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.repositories.memory_embeddings import GenerationStatus


class MemoryEmbeddingRead(BaseModel):
    """Embedding metadata that intentionally excludes vector values."""

    id: uuid.UUID
    memory_id: uuid.UUID
    provider: str
    model: str
    dimensions: int
    input_hash: str
    embedded_at: datetime
    created_at: datetime
    updated_at: datetime
    generation_status: GenerationStatus
