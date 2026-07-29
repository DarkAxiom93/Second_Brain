"""Canonicalization and persistence workflow for Memory embeddings."""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings.openai_provider import validate_embedding
from app.embeddings.provider import EmbeddingProvider
from app.models.memory import Memory
from app.models.memory_embedding import MemoryEmbedding

GenerationStatus = Literal["created", "updated", "unchanged"]


@dataclass(frozen=True)
class GenerationResult:
    """Embedding row paired with the action taken in this workflow."""

    embedding: MemoryEmbedding
    generation_status: GenerationStatus


def normalize_line_endings(value: str) -> str:
    """Normalize CRLF and CR while preserving all other whitespace."""

    return value.replace("\r\n", "\n").replace("\r", "\n")


def canonical_memory_text(memory: Memory) -> str:
    """Build the exact stable provider input from the four approved fields."""

    title = normalize_line_endings(memory.title or "")
    summary = normalize_line_endings(memory.summary or "")
    content = normalize_line_endings(memory.content)
    source = normalize_line_endings(memory.source or "")
    return (
        f"TITLE:\n{title}\n\nSUMMARY:\n{summary}\n\n"
        f"CONTENT:\n{content}\n\nSOURCE:\n{source}"
    )


def canonical_input_hash(text: str) -> str:
    """Calculate lowercase SHA-256 over the exact UTF-8 provider input."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_embedding(session: Session, memory_id: uuid.UUID) -> MemoryEmbedding | None:
    return session.scalar(
        select(MemoryEmbedding).where(MemoryEmbedding.memory_id == memory_id)
    )


def generate_memory_embedding(
    session: Session, memory: Memory, provider: EmbeddingProvider
) -> GenerationResult:
    """Generate or idempotently update one embedding without committing."""

    text = canonical_memory_text(memory)
    input_hash = canonical_input_hash(text)
    existing = get_embedding(session, memory.id)
    identity = (provider.name, provider.model, provider.dimensions, input_hash)
    if (
        existing is not None
        and (
            existing.provider,
            existing.model,
            existing.dimensions,
            existing.input_hash,
        )
        == identity
    ):
        return GenerationResult(existing, "unchanged")

    vector = validate_embedding(provider.embed(text), provider.dimensions)
    now = datetime.now(UTC)
    if existing is None:
        existing = MemoryEmbedding(memory_id=memory.id)
        session.add(existing)
        generation_status: GenerationStatus = "created"
    else:
        generation_status = "updated"
    existing.provider = provider.name
    existing.model = provider.model
    existing.dimensions = provider.dimensions
    existing.embedding = vector
    existing.input_hash = input_hash
    existing.embedded_at = now
    session.flush()
    session.refresh(existing)
    return GenerationResult(existing, generation_status)
