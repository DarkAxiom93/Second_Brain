"""Focused schema, provider, and route tests for embedding batches."""

import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routes.memory_embedding_batches import (
    configured_embedding_identity,
    provider_resolver,
)
from app.db.dependencies import get_db_session
from app.main import create_app
from app.schemas.memory_embedding import (
    MemoryEmbeddingBatchRequest,
    MemoryEmbeddingReembedRequest,
)


@pytest.mark.parametrize(
    ("body", "valid"),
    [
        ({"scope": "project", "project_id": str(uuid.uuid4())}, True),
        ({"scope": "project"}, False),
        ({"scope": "unassigned"}, True),
        ({"scope": "unassigned", "project_id": str(uuid.uuid4())}, False),
        ({"scope": "all"}, True),
        ({"scope": "all", "project_id": str(uuid.uuid4())}, False),
        ({"scope": "other"}, False),
        ({"scope": "all", "unknown": 1}, False),
        ({"scope": "all", "limit": 0}, False),
        ({"scope": "all", "limit": 51}, False),
    ],
)
def test_request_validation(body: dict[str, object], valid: bool) -> None:
    if valid:
        request = MemoryEmbeddingBatchRequest.model_validate(body)
        assert 1 <= request.limit <= 50
    else:
        with pytest.raises(ValidationError):
            MemoryEmbeddingBatchRequest.model_validate(body)


def test_empty_batch_never_resolves_provider_or_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock()
    resolver = Mock()
    monkeypatch.setattr(
        "app.memory_embedding_batch.repository.select_candidates", Mock(return_value=[])
    )
    application = create_app()
    application.dependency_overrides[get_db_session] = lambda: session
    application.dependency_overrides[provider_resolver] = lambda: resolver
    response = TestClient(application).post(
        "/memory-embeddings/batch",
        json={"scope": "project", "project_id": str(uuid.uuid4())},
    )
    assert response.status_code == 200
    assert response.json() == {
        "batch_status": "empty",
        "selected_count": 0,
        "created_count": 0,
        "unchanged_count": 0,
        "skipped_count": 0,
        "items": [],
    }
    resolver.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()


@pytest.mark.parametrize(
    ("body", "valid"),
    [
        ({"scope": "all", "selection": "stale"}, True),
        ({"scope": "all", "selection": "all", "limit": 50}, True),
        ({"scope": "all", "selection": "other"}, False),
        ({"scope": "project", "selection": "stale"}, False),
        (
            {
                "scope": "unassigned",
                "project_id": str(uuid.uuid4()),
                "selection": "stale",
            },
            False,
        ),
        ({"scope": "all", "selection": "stale", "extra": True}, False),
    ],
)
def test_reembed_request_validation(body: dict[str, object], valid: bool) -> None:
    if valid:
        MemoryEmbeddingReembedRequest.model_validate(body)
    else:
        with pytest.raises(ValidationError):
            MemoryEmbeddingReembedRequest.model_validate(body)


def test_empty_reembed_never_resolves_provider_or_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock()
    resolver = Mock()
    monkeypatch.setattr(
        "app.memory_embedding_reembedding.repository.select_reembedding_candidates",
        Mock(return_value=[]),
    )
    application = create_app()
    application.dependency_overrides[get_db_session] = lambda: session
    application.dependency_overrides[provider_resolver] = lambda: resolver
    application.dependency_overrides[configured_embedding_identity] = lambda: (
        "fake",
        "fixed-1536",
        1536,
    )
    response = TestClient(application).post(
        "/memory-embeddings/reembed",
        json={
            "scope": "project",
            "project_id": str(uuid.uuid4()),
            "selection": "stale",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "batch_status": "empty",
        "selected_count": 0,
        "updated_count": 0,
        "unchanged_count": 0,
        "skipped_count": 0,
        "items": [],
    }
    resolver.assert_not_called()
    session.commit.assert_not_called()
