"""Typed extraction provider contract and untrusted output models."""

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

MemoryType = Literal[
    "working",
    "episodic",
    "semantic",
    "decision",
    "procedural",
    "preference",
    "temporary",
]


class ChunkSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    chunk_index: int
    content: str
    content_hash: str
    char_start: int
    char_end: int
    locator: str | None


class ExtractedProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None
    summary: str | None
    content: str
    memory_type: MemoryType
    importance: float
    confidence: float
    evidence_text: str
    evidence_start: int
    evidence_end: int


class ChunkExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_index: int
    proposals: list[ExtractedProposal]


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunks: list[ChunkExtraction]


class ExtractionProvider(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def model(self) -> str: ...
    @property
    def prompt_version(self) -> str: ...
    def extract(
        self,
        instructions: str,
        chunks: list[ChunkSnapshot],
        max_proposals_per_chunk: int,
    ) -> ExtractionResult: ...


class ProviderUnavailableError(Exception):
    pass


class ProviderRequestError(Exception):
    pass


class InvalidExtractionResponseError(Exception):
    pass
