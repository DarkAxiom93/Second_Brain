"""Pure, deterministic normalization and fixed-character chunking."""

from dataclasses import dataclass
from hashlib import sha256

MAX_CHUNKS = 10_000


@dataclass(frozen=True)
class TextChunk:
    """One exact character range from normalized text."""

    chunk_index: int
    content: str
    char_start: int
    char_end: int
    content_hash: str
    locator: None = None


def normalize_plain_text(text: str) -> str:
    """Normalize line endings to LF while preserving every other character."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def hash_chunk(content: str) -> str:
    """Return the lowercase SHA-256 digest of exact UTF-8 content."""
    return sha256(content.encode("utf-8")).hexdigest()


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[TextChunk]:
    """Split normalized text into deterministic, overlapping character ranges."""
    if chunk_size <= 0 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk settings do not permit forward progress")

    chunks: list[TextChunk] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        content = text[start:end]
        if content.strip():
            if len(chunks) >= MAX_CHUNKS:
                raise ValueError("text produces more than 10000 chunks")
            chunks.append(
                TextChunk(
                    chunk_index=len(chunks),
                    content=content,
                    char_start=start,
                    char_end=end,
                    content_hash=hash_chunk(content),
                )
            )
        if end == len(text):
            break
        next_start = end - chunk_overlap
        if next_start <= start:
            raise ValueError("chunk settings do not permit forward progress")
        start = next_start

    if not chunks:
        raise ValueError("text must contain a non-whitespace character")
    return chunks
