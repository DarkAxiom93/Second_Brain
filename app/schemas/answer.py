"""Public evidence-backed answer schemas."""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.memory import MemoryRead

AnswerStatus = Literal["answered", "insufficient_evidence"]
AnswerSearchMode = Literal["lexical", "semantic", "hybrid"]


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ]
    project_id: uuid.UUID | None = None
    search_mode: AnswerSearchMode = "hybrid"
    limit: Annotated[int, Field(ge=1, le=20)] = 10


class AnswerCitation(BaseModel):
    label: str
    rank: int
    memory: MemoryRead
    lexical_score: float | None
    semantic_score: float | None


class AnswerRead(BaseModel):
    answer_status: AnswerStatus
    answer: str
    search_mode: AnswerSearchMode
    citations: list[AnswerCitation]
