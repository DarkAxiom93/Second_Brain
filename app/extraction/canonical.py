"""Deterministic extraction inputs, validation, and proposal hashes."""

import hashlib
import json
import math
import uuid
from dataclasses import dataclass

from app.extraction.provider import (
    ChunkSnapshot,
    ExtractionResult,
    InvalidExtractionResponseError,
)

MAX_INPUT_BYTES = 250_000
MAX_CONTENT_LENGTH = 50_000


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def normalize_lf(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def canonical_input(
    *,
    provider: str,
    model: str,
    prompt_version: str,
    project_id: uuid.UUID | None,
    max_proposals_per_chunk: int,
    chunks: list[ChunkSnapshot],
) -> tuple[bytes, str, list[ChunkSnapshot]]:
    normalized = [
        chunk.model_copy(update={"content": normalize_lf(chunk.content)})
        for chunk in chunks
    ]
    payload = {
        "provider": provider,
        "model": model,
        "prompt_version": prompt_version,
        "project_id": str(project_id) if project_id else None,
        "max_proposals_per_chunk": max_proposals_per_chunk,
        "chunks": [c.model_dump() for c in normalized],
    }
    data = _json_bytes(payload)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("extraction input too large")
    return data, hashlib.sha256(data).hexdigest(), normalized


@dataclass(frozen=True)
class ValidatedProposal:
    chunk: ChunkSnapshot
    proposal_index: int
    title: str | None
    summary: str | None
    content: str
    memory_type: str
    importance: float
    confidence: float
    evidence_text: str
    evidence_char_start: int
    evidence_char_end: int
    proposal_hash: str


def _optional(value: str | None, maximum: int | None = None) -> str | None:
    if value is None or not value.strip():
        return None
    result = value.strip()
    if maximum is not None and len(result) > maximum:
        raise InvalidExtractionResponseError
    return result


def validate_result(
    result: ExtractionResult,
    chunks: list[ChunkSnapshot],
    project_id: uuid.UUID | None,
    maximum: int,
) -> list[ValidatedProposal]:
    selected = {c.chunk_index: c for c in chunks}
    indexes = [item.chunk_index for item in result.chunks]
    if len(indexes) != len(set(indexes)) or set(indexes) != set(selected):
        raise InvalidExtractionResponseError
    output: list[ValidatedProposal] = []
    for item in result.chunks:
        chunk = selected[item.chunk_index]
        if len(item.proposals) > maximum:
            raise InvalidExtractionResponseError
        for index, proposal in enumerate(item.proposals):
            title, summary, content = (
                _optional(proposal.title, 255),
                _optional(proposal.summary),
                proposal.content.strip(),
            )
            if not content or len(content) > MAX_CONTENT_LENGTH:
                raise InvalidExtractionResponseError
            if not all(
                math.isfinite(v) and 0 <= v <= 1
                for v in (proposal.importance, proposal.confidence)
            ):
                raise InvalidExtractionResponseError
            start, end = proposal.evidence_start, proposal.evidence_end
            if (
                start < 0
                or end <= start
                or end > len(chunk.content)
                or not proposal.evidence_text.strip()
            ):
                raise InvalidExtractionResponseError
            if chunk.content[start:end] != proposal.evidence_text:
                raise InvalidExtractionResponseError
            absolute_start, absolute_end = (
                chunk.char_start + start,
                chunk.char_start + end,
            )
            canonical = {
                "source_chunk_hash": chunk.content_hash,
                "project_id": str(project_id) if project_id else None,
                "proposal_index": index,
                "title": title,
                "summary": summary,
                "content": content,
                "memory_type": proposal.memory_type,
                "importance": proposal.importance,
                "confidence": proposal.confidence,
                "evidence_text": proposal.evidence_text,
                "evidence_char_start": absolute_start,
                "evidence_char_end": absolute_end,
                "source_locator": chunk.locator,
            }
            output.append(
                ValidatedProposal(
                    chunk,
                    index,
                    title,
                    summary,
                    content,
                    proposal.memory_type,
                    proposal.importance,
                    proposal.confidence,
                    proposal.evidence_text,
                    absolute_start,
                    absolute_end,
                    hashlib.sha256(_json_bytes(canonical)).hexdigest(),
                )
            )
    return output
