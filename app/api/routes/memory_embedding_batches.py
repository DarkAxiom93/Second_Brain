"""Explicit synchronous batch Memory embedding endpoint."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.dependencies import get_db_session
from app.embeddings import (
    EmbeddingProvider,
    InvalidEmbeddingResponseError,
    ProviderRequestError,
    ProviderUnavailableError,
    get_embedding_provider,
)
from app.memory_embedding_batch import generate_batch
from app.memory_embedding_reembedding import reembed_batch
from app.schemas.memory_embedding import (
    MemoryEmbeddingBatchItem,
    MemoryEmbeddingBatchRead,
    MemoryEmbeddingBatchRequest,
    MemoryEmbeddingMetadata,
    MemoryEmbeddingReembedItem,
    MemoryEmbeddingReembedRead,
    MemoryEmbeddingReembedRequest,
)

router = APIRouter(prefix="/memory-embeddings", tags=["memory-embeddings"])


def provider_resolver() -> Callable[[], EmbeddingProvider]:
    return get_embedding_provider


def configured_embedding_identity() -> tuple[str, str, int]:
    settings = get_settings()
    return (
        settings.embedding_provider,
        settings.embedding_model,
        settings.embedding_dimensions,
    )


@router.post(
    "/batch", response_model=MemoryEmbeddingBatchRead, response_model_exclude_none=True
)
def generate_memory_embedding_batch(
    request: MemoryEmbeddingBatchRequest,
    session: Annotated[Session, Depends(get_db_session)],
    resolve_provider: Annotated[
        Callable[[], EmbeddingProvider], Depends(provider_resolver)
    ],
) -> MemoryEmbeddingBatchRead:
    """Generate missing active Memory embeddings in one explicit bounded batch."""

    try:
        items = generate_batch(session, request, resolve_provider)
        created_count = sum(item.generation_status == "created" for item in items)
        if created_count:
            session.commit()
        else:
            session.rollback()
    except ProviderUnavailableError:
        session.rollback()
        raise HTTPException(503, "embedding provider unavailable") from None
    except InvalidEmbeddingResponseError:
        session.rollback()
        raise HTTPException(502, "invalid embedding response") from None
    except ProviderRequestError:
        session.rollback()
        raise HTTPException(502, "embedding provider failed") from None
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(503, "database unavailable") from None

    public_items = []
    for item in items:
        metadata = (
            MemoryEmbeddingMetadata.model_validate(item.embedding, from_attributes=True)
            if item.embedding is not None
            else None
        )
        public_items.append(
            MemoryEmbeddingBatchItem(
                memory_id=item.memory_id,
                generation_status=item.generation_status,
                embedding=metadata,
                skipped_reason=item.skipped_reason,
            )
        )
    unchanged_count = sum(item.generation_status == "unchanged" for item in items)
    skipped_count = sum(item.generation_status == "skipped" for item in items)
    return MemoryEmbeddingBatchRead(
        batch_status="completed" if items else "empty",
        selected_count=len(items),
        created_count=created_count,
        unchanged_count=unchanged_count,
        skipped_count=skipped_count,
        items=public_items,
    )


@router.post(
    "/reembed",
    response_model=MemoryEmbeddingReembedRead,
    response_model_exclude_none=True,
)
def reembed_memory_embedding_batch(
    request: MemoryEmbeddingReembedRequest,
    session: Annotated[Session, Depends(get_db_session)],
    resolve_provider: Annotated[
        Callable[[], EmbeddingProvider], Depends(provider_resolver)
    ],
    expected_identity: Annotated[
        tuple[str, str, int], Depends(configured_embedding_identity)
    ],
) -> MemoryEmbeddingReembedRead:
    """Explicitly replace selected active existing Memory embeddings."""

    try:
        items = reembed_batch(session, request, resolve_provider, expected_identity)
        updated_count = sum(item.reembedding_status == "updated" for item in items)
        if updated_count:
            session.commit()
        else:
            session.rollback()
    except ProviderUnavailableError:
        session.rollback()
        raise HTTPException(503, "embedding provider unavailable") from None
    except InvalidEmbeddingResponseError:
        session.rollback()
        raise HTTPException(502, "invalid embedding response") from None
    except ProviderRequestError:
        session.rollback()
        raise HTTPException(502, "embedding provider failed") from None
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(503, "database unavailable") from None

    public_items = [
        MemoryEmbeddingReembedItem(
            memory_id=item.memory_id,
            reembedding_status=item.reembedding_status,
            previous_embedding=MemoryEmbeddingMetadata.model_validate(
                item.previous, from_attributes=True
            ),
            current_embedding=(
                MemoryEmbeddingMetadata.model_validate(
                    item.current, from_attributes=True
                )
                if item.current is not None
                else None
            ),
            skipped_reason=item.skipped_reason,
        )
        for item in items
    ]
    return MemoryEmbeddingReembedRead(
        batch_status="completed" if items else "empty",
        selected_count=len(items),
        updated_count=sum(item.reembedding_status == "updated" for item in items),
        unchanged_count=sum(item.reembedding_status == "unchanged" for item in items),
        skipped_count=sum(item.reembedding_status == "skipped" for item in items),
        items=public_items,
    )
