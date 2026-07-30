"""Explicit synchronous batch Memory embedding workflow."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.embeddings.openai_provider import validate_embedding
from app.embeddings.provider import EmbeddingProvider, InvalidEmbeddingResponseError
from app.models.memory_embedding import MemoryEmbedding
from app.repositories import memory_embedding_batches as repository
from app.repositories.memory_embeddings import (
    canonical_input_hash,
    canonical_memory_text,
)
from app.schemas.memory_embedding import MemoryEmbeddingBatchRequest


@dataclass(frozen=True)
class BatchItem:
    memory_id: uuid.UUID
    generation_status: Literal["created", "unchanged", "skipped"]
    embedding: MemoryEmbedding | None
    skipped_reason: str | None = None


def generate_batch(
    session: Session,
    request: MemoryEmbeddingBatchRequest,
    resolve_provider: Callable[[], EmbeddingProvider],
) -> list[BatchItem]:
    candidates = repository.select_candidates(session, **request.model_dump())
    if not candidates:
        return []
    provider = resolve_provider()
    texts = [canonical_memory_text(memory) for memory in candidates]
    raw_vectors = provider.embed_many(texts)
    if not isinstance(raw_vectors, list) or len(raw_vectors) != len(candidates):
        raise InvalidEmbeddingResponseError
    vectors = [
        validate_embedding(vector, provider.dimensions) for vector in raw_vectors
    ]
    locked = repository.lock_memories(session, [memory.id for memory in candidates])
    existing = repository.embeddings_for(session, [memory.id for memory in candidates])
    now = datetime.now(UTC)
    items: list[BatchItem] = []
    for memory, text, vector in zip(candidates, texts, vectors, strict=True):
        current = locked[memory.id]
        if current.status != "active":
            items.append(BatchItem(memory.id, "skipped", None, "memory_not_active"))
        elif memory.id in existing:
            items.append(BatchItem(memory.id, "unchanged", existing[memory.id]))
        else:
            row, created = repository.insert_embedding_if_missing(
                session,
                memory_id=memory.id,
                provider=provider.name,
                model=provider.model,
                dimensions=provider.dimensions,
                embedding=vector,
                input_hash=canonical_input_hash(text),
                embedded_at=now,
            )
            if created:
                items.append(BatchItem(memory.id, "created", row))
            else:
                items.append(BatchItem(memory.id, "unchanged", row))
    return items
