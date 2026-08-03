"""Focused contract coverage for deterministic explained Memory search."""

import math
import uuid
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.api.routes import memories as memory_routes
from app.db.dependencies import get_db_session
from app.embeddings.provider import ProviderRequestError, ProviderUnavailableError
from app.main import create_app
from app.models.memory import Memory
from app.repositories.memories import ExplainedMemorySearchResult
from app.schemas.memory import (
    ExplainedMemorySearchRequest,
    MemorySearchExplanationRead,
)


def stored_memory() -> Memory:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    return Memory(
        id=uuid.uuid4(),
        content="ranked memory",
        memory_type="semantic",
        importance=0.5,
        confidence=1.0,
        status="active",
        created_at=timestamp,
        updated_at=timestamp,
    )


@pytest.mark.parametrize("mode", ["lexical", "semantic", "hybrid"])
def test_request_requires_exact_fields_and_accepts_all_modes(mode: str) -> None:
    request = ExplainedMemorySearchRequest.model_validate(
        {
            "query": "  q  ",
            "mode": mode,
            "filters": {},
            "pagination": {"limit": 1, "offset": 0},
        }
    )
    assert request.query == "q"
    assert request.mode == mode


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "q", "mode": "lexical", "filters": {}},
        {"query": "q", "mode": "lexical", "pagination": {}},
        {"query": "q", "mode": "invalid", "filters": {}, "pagination": {}},
        {"query": " ", "mode": "lexical", "filters": {}, "pagination": {}},
        {"query": "x" * 501, "mode": "lexical", "filters": {}, "pagination": {}},
        {
            "query": "q",
            "mode": "lexical",
            "filters": {},
            "pagination": {},
            "extra": True,
        },
        {"query": "q", "mode": "lexical", "pagination": {"limit": 0}},
        {"query": "q", "mode": "lexical", "filters": {"importance_min": 2}},
    ],
)
def test_request_rejects_missing_invalid_and_extra_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ExplainedMemorySearchRequest.model_validate(payload)


@pytest.mark.parametrize("field", ["lexical_signal", "semantic_signal"])
@pytest.mark.parametrize("value", [-0.1, 1.1, math.inf, -math.inf, math.nan])
def test_response_rejects_invalid_public_signals(field: str, value: float) -> None:
    data = {
        "mode": "lexical",
        "matched_by": ["lexical"],
        "lexical_rank": 1,
        "semantic_rank": None,
        "lexical_signal": 0.5,
        "semantic_signal": None,
        "lexical_rrf_contribution": None,
        "semantic_rrf_contribution": None,
        "fused_rrf_score": None,
    }
    data[field] = value
    with pytest.raises(ValidationError):
        MemorySearchExplanationRead.model_validate(data)


def test_lexical_route_never_resolves_provider_and_returns_bounded_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock()
    application = create_app()
    application.dependency_overrides[get_db_session] = lambda: session
    provider = Mock(side_effect=AssertionError("provider resolved"))
    monkeypatch.setattr(memory_routes, "provider_dependency", provider)
    item = ExplainedMemorySearchResult(
        rank=3,
        memory=stored_memory(),
        lexical_rank=3,
        semantic_rank=None,
        lexical_score=3.0,
        semantic_distance=None,
        lexical_rrf_contribution=None,
        semantic_rrf_contribution=None,
        fused_rrf_score=None,
    )
    repository = Mock(return_value=[item])
    monkeypatch.setattr(
        memory_routes.memory_repository, "search_memories_explained", repository
    )

    response = TestClient(application).post(
        "/memories/search/explained",
        json={
            "query": "  ranked  ",
            "mode": "lexical",
            "filters": {},
            "pagination": {},
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["rank"] == 3
    explanation = response.json()[0]["explanation"]
    assert explanation == {
        "mode": "lexical",
        "matched_by": ["lexical"],
        "lexical_rank": 3,
        "semantic_rank": None,
        "lexical_signal": 0.75,
        "semantic_signal": None,
        "lexical_rrf_contribution": None,
        "semantic_rrf_contribution": None,
        "fused_rrf_score": None,
    }
    provider.assert_not_called()
    session.flush.assert_not_called()
    session.commit.assert_not_called()


def test_semantic_provider_and_safe_failure_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock()
    application = create_app()
    application.dependency_overrides[get_db_session] = lambda: session
    provider = Mock()
    provider.embed.return_value = [1.0, *([0.0] * 1535)]
    monkeypatch.setattr(
        memory_routes, "provider_dependency", Mock(return_value=provider)
    )
    repository = Mock(return_value=[])
    monkeypatch.setattr(
        memory_routes.memory_repository, "search_memories_explained", repository
    )
    client = TestClient(application)
    payload = {"query": "meaning", "mode": "semantic", "filters": {}, "pagination": {}}

    assert client.post("/memories/search/explained", json=payload).json() == []
    provider.embed.assert_called_once_with("meaning")

    provider.embed.side_effect = ProviderRequestError("secret")
    response = client.post("/memories/search/explained", json=payload)
    assert response.status_code == 502
    assert response.json() == {"detail": "embedding provider failed"}

    monkeypatch.setattr(
        memory_routes,
        "provider_dependency",
        Mock(side_effect=ProviderUnavailableError("secret")),
    )
    response = client.post("/memories/search/explained", json=payload)
    assert response.status_code == 503
    assert response.json() == {"detail": "embedding provider unavailable"}


def test_database_failure_is_safe_and_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock()
    application = create_app()
    application.dependency_overrides[get_db_session] = lambda: session
    monkeypatch.setattr(
        memory_routes.memory_repository,
        "search_memories_explained",
        Mock(side_effect=OperationalError("SQL secret", {}, Exception("password"))),
    )
    response = TestClient(application).post(
        "/memories/search/explained",
        json={"query": "q", "mode": "lexical", "filters": {}, "pagination": {}},
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert "secret" not in response.text
    session.flush.assert_not_called()
    session.commit.assert_not_called()
