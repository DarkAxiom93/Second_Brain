"""Focused unit coverage for explicit semantic Memory search."""

from collections.abc import Generator
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.routes import memories as memory_routes
from app.db.dependencies import get_db_session
from app.embeddings.provider import ProviderRequestError
from app.main import create_app


class FakeProvider:
    name = "fake"
    model = "fixed"
    dimensions = 1536

    def __init__(self, vector: list[float] | None = None) -> None:
        self.vector = vector if vector is not None else [0.0] * 1536
        self.inputs: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.inputs.append(text)
        return self.vector


@pytest.fixture
def search_setup() -> tuple[TestClient, Mock, FakeProvider, Mock]:
    session = Mock()
    provider = FakeProvider()
    repository_call = Mock(return_value=[])

    def override_session() -> Generator[Mock, None, None]:
        yield session

    application = create_app()
    application.dependency_overrides[get_db_session] = override_session
    application.dependency_overrides[memory_routes.provider_dependency] = lambda: (
        provider
    )
    client = TestClient(application)
    return client, session, provider, repository_call


def test_valid_request_trims_embeds_once_and_passes_filters_and_pagination(
    monkeypatch: pytest.MonkeyPatch,
    search_setup: tuple[TestClient, Mock, FakeProvider, Mock],
) -> None:
    client, session, provider, repository_call = search_setup
    monkeypatch.setattr(
        memory_routes.memory_repository, "search_memories", repository_call
    )
    response = client.post(
        "/memories/search",
        json={
            "query": "  exact query  ",
            "filters": {"memory_type": "decision", "importance_min": 0.4},
            "pagination": {"limit": 7, "offset": 2},
        },
    )
    assert response.status_code == 200
    assert response.json() == []
    assert provider.inputs == ["exact query"]
    repository_call.assert_called_once()
    assert repository_call.call_args.args == (session,)
    assert repository_call.call_args.kwargs["query_vector"] == [0.0] * 1536
    assert repository_call.call_args.kwargs["memory_type"] == "decision"
    assert repository_call.call_args.kwargs["importance_min"] == 0.4
    assert repository_call.call_args.kwargs["limit"] == 7
    assert repository_call.call_args.kwargs["offset"] == 2


@pytest.mark.parametrize("mode", [None, "semantic"])
def test_semantic_mode_is_default_and_backward_compatible(
    mode: str | None,
    monkeypatch: pytest.MonkeyPatch,
    search_setup: tuple[TestClient, Mock, FakeProvider, Mock],
) -> None:
    client, _, provider, repository_call = search_setup
    monkeypatch.setattr(
        memory_routes.memory_repository, "search_memories", repository_call
    )
    payload = {"query": "  meaning  "}
    if mode is not None:
        payload["mode"] = mode
    response = client.post("/memories/search", json=payload)
    assert response.status_code == 200
    assert provider.inputs == ["meaning"]
    repository_call.assert_called_once()


def test_hybrid_mode_embeds_once_and_passes_trimmed_query(
    monkeypatch: pytest.MonkeyPatch,
    search_setup: tuple[TestClient, Mock, FakeProvider, Mock],
) -> None:
    client, session, provider, _ = search_setup
    hybrid_call = Mock(return_value=[])
    monkeypatch.setattr(
        memory_routes.memory_repository, "search_memories_hybrid", hybrid_call
    )
    response = client.post(
        "/memories/search",
        json={"query": "  exact hybrid  ", "mode": "hybrid"},
    )
    assert response.status_code == 200
    assert provider.inputs == ["exact hybrid"]
    hybrid_call.assert_called_once()
    assert hybrid_call.call_args.args == (session,)
    assert hybrid_call.call_args.kwargs["query"] == "exact hybrid"
    assert hybrid_call.call_args.kwargs["query_vector"] == [0.0] * 1536


def test_invalid_mode_returns_422_without_provider_call(
    search_setup: tuple[TestClient, Mock, FakeProvider, Mock],
) -> None:
    client, _, provider, _ = search_setup
    response = client.post(
        "/memories/search", json={"query": "valid", "mode": "lexical"}
    )
    assert response.status_code == 422
    assert provider.inputs == []


@pytest.mark.parametrize("query", ["   ", "x" * 501])
def test_invalid_query_returns_422_without_provider_call(
    query: str, search_setup: tuple[TestClient, Mock, FakeProvider, Mock]
) -> None:
    client, _, provider, _ = search_setup
    assert client.post("/memories/search", json={"query": query}).status_code == 422
    assert provider.inputs == []


@pytest.mark.parametrize(
    "filters",
    [
        {"importance_min": 0.8, "importance_max": 0.2},
        {"confidence_min": 0.8, "confidence_max": 0.2},
        {
            "event_time_from": "2026-02-01T00:00:00Z",
            "event_time_to": "2026-01-01T00:00:00Z",
        },
        {"created_at_from": "2026-01-01T00:00:00"},
        {"memory_type": "unknown"},
    ],
)
def test_existing_filter_validation_is_reused(
    filters: dict[str, object],
    search_setup: tuple[TestClient, Mock, FakeProvider, Mock],
) -> None:
    client, _, provider, _ = search_setup
    response = client.post(
        "/memories/search", json={"query": "valid", "filters": filters}
    )
    assert response.status_code == 422
    assert provider.inputs == []


@pytest.mark.parametrize(
    ("vector", "detail"),
    [
        ([0.0] * 1535, "invalid embedding response"),
        ([float("nan")] * 1536, "invalid embedding response"),
    ],
)
def test_malformed_vectors_return_exact_502(
    vector: list[float],
    detail: str,
    search_setup: tuple[TestClient, Mock, FakeProvider, Mock],
) -> None:
    client, _, provider, _ = search_setup
    provider.vector = vector
    response = client.post("/memories/search", json={"query": "valid"})
    assert response.status_code == 502
    assert response.json() == {"detail": detail}


def test_provider_and_database_failures_are_generic(
    monkeypatch: pytest.MonkeyPatch,
    search_setup: tuple[TestClient, Mock, FakeProvider, Mock],
) -> None:
    client, _, provider, _ = search_setup
    provider.embed = Mock(side_effect=ProviderRequestError("api_key=secret"))
    response = client.post("/memories/search", json={"query": "valid"})
    assert response.status_code == 502
    assert response.json() == {"detail": "embedding provider failed"}
    assert "secret" not in response.text

    provider.embed = Mock(return_value=[0.0] * 1536)
    failure = OperationalError("sensitive SQL", {}, Exception("password=secret"))
    monkeypatch.setattr(
        memory_routes.memory_repository,
        "search_memories",
        Mock(side_effect=failure),
    )
    response = client.post("/memories/search", json={"query": "valid"})
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert "secret" not in response.text and "sensitive" not in response.text


def test_missing_provider_configuration_is_exact_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()
    response = TestClient(create_app()).post(
        "/memories/search", json={"query": "valid"}
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "embedding provider unavailable"}
    get_settings.cache_clear()
