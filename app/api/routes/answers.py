"""Explicit evidence-backed Memory answer endpoint."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.answers.dependencies import get_answer_provider
from app.answers.provider import (
    AnswerProvider,
    InvalidAnswerResponseError,
)
from app.answers.provider import (
    ProviderRequestError as AnswerProviderRequestError,
)
from app.answers.provider import (
    ProviderUnavailableError as AnswerProviderUnavailableError,
)
from app.answers.service import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    answer_from_evidence,
)
from app.db.dependencies import get_db_session
from app.embeddings.dependencies import get_embedding_provider
from app.embeddings.openai_provider import validate_embedding
from app.embeddings.provider import (
    EmbeddingProvider,
    InvalidEmbeddingResponseError,
)
from app.embeddings.provider import (
    ProviderRequestError as EmbeddingProviderRequestError,
)
from app.embeddings.provider import (
    ProviderUnavailableError as EmbeddingProviderUnavailableError,
)
from app.repositories.memories import search_answer_evidence
from app.schemas.answer import AnswerCitation, AnswerRead, AnswerRequest
from app.schemas.memory import MemoryRead

router = APIRouter(prefix="/answers", tags=["answers"])


def answer_provider_resolver() -> Callable[[], AnswerProvider]:
    """Inject a lazy resolver so empty evidence never resolves a provider."""

    return get_answer_provider


def embedding_provider_resolver() -> Callable[[], EmbeddingProvider]:
    """Inject a lazy resolver so lexical mode never resolves a provider."""

    return get_embedding_provider


@router.post(
    "",
    response_model=AnswerRead,
    responses={
        422: {"description": "Validation failure"},
        502: {"description": "Provider failure or invalid provider response"},
        503: {"description": "Database or provider unavailable"},
    },
)
def create_answer(
    request: AnswerRequest,
    session: Annotated[Session, Depends(get_db_session)],
    resolve_answer_provider: Annotated[
        Callable[[], AnswerProvider], Depends(answer_provider_resolver)
    ],
    resolve_embedding_provider: Annotated[
        Callable[[], EmbeddingProvider], Depends(embedding_provider_resolver)
    ],
) -> AnswerRead:
    """Answer one question solely from bounded, active Memory evidence."""

    query_vector: list[float] | None = None
    if request.search_mode != "lexical":
        try:
            embedding_provider = resolve_embedding_provider()
            query_vector = validate_embedding(
                embedding_provider.embed(request.query), 1536
            )
        except EmbeddingProviderUnavailableError:
            raise HTTPException(503, "embedding provider unavailable") from None
        except InvalidEmbeddingResponseError:
            raise HTTPException(502, "invalid embedding response") from None
        except EmbeddingProviderRequestError:
            raise HTTPException(502, "embedding provider failed") from None
    try:
        evidence = search_answer_evidence(
            session,
            query=request.query,
            mode=request.search_mode,
            project_id=request.project_id,
            limit=request.limit,
            query_vector=query_vector,
        )
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(503, "database unavailable") from None
    if not evidence:
        session.rollback()
        return AnswerRead(
            answer_status="insufficient_evidence",
            answer=INSUFFICIENT_EVIDENCE_MESSAGE,
            search_mode=request.search_mode,
            citations=[],
        )
    try:
        provider = resolve_answer_provider()
        result = answer_from_evidence(
            query=request.query,
            evidence=evidence,
            provider=provider,
        )
    except AnswerProviderUnavailableError:
        session.rollback()
        raise HTTPException(503, "answer provider unavailable") from None
    except (AnswerProviderRequestError, InvalidAnswerResponseError, ValueError):
        session.rollback()
        raise HTTPException(502, "answer provider failed") from None
    session.rollback()
    cited_ids = {item.memory.id for item in result.citations}
    return AnswerRead(
        answer_status=result.answer_status,  # type: ignore[arg-type]
        answer=result.answer,
        search_mode=request.search_mode,
        citations=[
            AnswerCitation(
                label=f"M{rank}",
                rank=rank,
                memory=MemoryRead.model_validate(item.memory),
                lexical_score=item.lexical_score,
                semantic_score=item.semantic_score,
            )
            for rank, item in enumerate(evidence, 1)
            if item.memory.id in cited_ids
        ],
    )
