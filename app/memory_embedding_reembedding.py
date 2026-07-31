"""Explicit synchronous batch Memory re-embedding workflow."""

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
from app.schemas.memory_embedding import MemoryEmbeddingReembedRequest


@dataclass(frozen=True)
class EmbeddingMetadata:
    id: uuid.UUID
    memory_id: uuid.UUID
    provider: str
    model: str
    dimensions: int
    input_hash: str
    embedded_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ReembeddingItem:
    memory_id: uuid.UUID
    reembedding_status: Literal["updated", "unchanged", "skipped"]
    previous: EmbeddingMetadata
    current: EmbeddingMetadata | None
    skipped_reason: Literal["memory_not_active", "embedding_missing"] | None = None


def metadata(row: MemoryEmbedding) -> EmbeddingMetadata:
    return EmbeddingMetadata(
        row.id,
        row.memory_id,
        row.provider,
        row.model,
        row.dimensions,
        row.input_hash,
        row.embedded_at,
        row.created_at,
        row.updated_at,
    )


def reembed_batch(
    session: Session,
    request: MemoryEmbeddingReembedRequest,
    resolve_provider: Callable[[], EmbeddingProvider],
    expected_identity: tuple[str, str, int],
) -> list[ReembeddingItem]:
    """Replace a bounded selected set after complete provider validation."""

    candidates = repository.select_reembedding_candidates(
        session,
        **request.model_dump(),
        provider=expected_identity[0],
        model=expected_identity[1],
        dimensions=expected_identity[2],
    )
    if not candidates:
        return []
    snapshots = {
        memory.id: metadata(memory.embedding_record)
        for memory in candidates
        if memory.embedding_record is not None
    }
    provider = resolve_provider()
    if (provider.name, provider.model, provider.dimensions) != expected_identity:
        raise InvalidEmbeddingResponseError
    texts = [canonical_memory_text(memory) for memory in candidates]
    hashes = [canonical_input_hash(text) for text in texts]
    raw_vectors = provider.embed_many(texts)
    if not isinstance(raw_vectors, list) or len(raw_vectors) != len(candidates):
        raise InvalidEmbeddingResponseError
    vectors = [
        validate_embedding(vector, provider.dimensions) for vector in raw_vectors
    ]

    ids = [memory.id for memory in candidates]
    locked_memories = repository.lock_memories(session, ids)
    locked_embeddings = repository.lock_embeddings(session, ids)
    now = datetime.now(UTC)
    items: list[ReembeddingItem] = []
    identity_prefix = (provider.name, provider.model, provider.dimensions)
    for candidate, vector, produced_hash in zip(
        candidates, vectors, hashes, strict=True
    ):
        memory = locked_memories[candidate.id]
        row = locked_embeddings.get(candidate.id)
        if row is None:
            snapshot = snapshots[candidate.id]
            items.append(
                ReembeddingItem(
                    candidate.id,
                    "skipped",
                    snapshot,
                    None,
                    "embedding_missing",
                )
            )
            continue
        before = metadata(row)
        if memory.status != "active":
            items.append(
                ReembeddingItem(
                    candidate.id, "skipped", before, before, "memory_not_active"
                )
            )
            continue
        current_text = canonical_memory_text(memory)
        current_hash = canonical_input_hash(current_text)
        current_identity = (row.provider, row.model, row.dimensions, row.input_hash)
        current_expected_identity = (*identity_prefix, current_hash)
        if current_hash != produced_hash:
            items.append(ReembeddingItem(candidate.id, "unchanged", before, before))
            continue
        exact_produced = (
            current_identity == (*identity_prefix, produced_hash)
            and list(row.embedding) == vector
        )
        eligible = (
            request.selection == "all" or current_identity != current_expected_identity
        )
        if not eligible or (request.selection == "all" and exact_produced):
            items.append(ReembeddingItem(candidate.id, "unchanged", before, before))
            continue
        row.provider, row.model, row.dimensions = identity_prefix
        row.embedding = vector
        row.input_hash = produced_hash
        row.embedded_at = now
        session.flush()
        session.refresh(row)
        items.append(ReembeddingItem(candidate.id, "updated", before, metadata(row)))
    return items
