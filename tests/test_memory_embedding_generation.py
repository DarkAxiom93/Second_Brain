"""Focused unit coverage for explicit Memory embedding generation."""

import hashlib
import uuid
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.routes.memories import provider_dependency
from app.db.dependencies import get_db_session
from app.embeddings.openai_provider import validate_embedding
from app.embeddings.provider import InvalidEmbeddingResponseError, ProviderRequestError
from app.main import create_app
from app.models.memory import Memory
from app.models.memory_embedding import MemoryEmbedding
from app.repositories import memory_embeddings as repository


class FakeProvider:
    name = "fake"
    model = "fixed-model"
    dimensions = 1536

    def __init__(self) -> None:
        self.inputs: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.inputs.append(text)
        return [0.25] * self.dimensions


def stored_memory() -> Memory:
    now = datetime.now(UTC)
    return Memory(
        id=uuid.uuid4(),
        content="body\rline",
        title="A\r\nB",
        summary=None,
        source=" note ",
        created_at=now,
        updated_at=now,
    )


def test_canonical_format_and_hash_are_exact_and_deterministic() -> None:
    memory = stored_memory()
    expected = "TITLE:\nA\nB\n\nSUMMARY:\n\n\nCONTENT:\nbody\nline\n\nSOURCE:\n note "
    assert repository.canonical_memory_text(memory) == expected
    expected_hash = hashlib.sha256(expected.encode("utf-8")).hexdigest()
    assert repository.canonical_input_hash(expected) == expected_hash
    memory.importance = 0.1
    memory.confidence = 0.2
    memory.status = "archived"
    memory.project_id = uuid.uuid4()
    assert (
        repository.canonical_input_hash(repository.canonical_memory_text(memory))
        == expected_hash
    )


@pytest.mark.parametrize("field", ["title", "summary", "content", "source"])
def test_each_canonical_field_changes_input_hash(field: str) -> None:
    memory = stored_memory()
    before = repository.canonical_input_hash(repository.canonical_memory_text(memory))
    setattr(memory, field, "different")
    after = repository.canonical_input_hash(repository.canonical_memory_text(memory))
    assert after != before


@pytest.mark.parametrize(
    "vector",
    [
        [],
        [0.0] * 1535,
        [0.0] * 1537,
        [float("nan")] * 1536,
        [float("inf")] * 1536,
        ["0"] * 1536,
        [True] * 1536,
    ],
)
def test_invalid_vectors_are_rejected(vector: list[object]) -> None:
    with pytest.raises(InvalidEmbeddingResponseError):
        validate_embedding(vector, 1536)


def test_repository_created_updated_unchanged_and_never_commits() -> None:
    memory = stored_memory()
    session = Mock()
    session.scalar.return_value = None
    provider = FakeProvider()
    created = repository.generate_memory_embedding(session, memory, provider)
    assert created.generation_status == "created"
    assert created.embedding.provider == "fake"
    assert created.embedding.model == "fixed-model"
    assert created.embedding.dimensions == 1536
    assert created.embedding.input_hash == repository.canonical_input_hash(
        provider.inputs[0]
    )
    session.commit.assert_not_called()

    session.scalar.return_value = created.embedding
    unchanged = repository.generate_memory_embedding(session, memory, provider)
    assert unchanged.generation_status == "unchanged"
    assert len(provider.inputs) == 1
    memory.content = "changed"
    updated = repository.generate_memory_embedding(session, memory, provider)
    assert updated.generation_status == "updated"
    assert updated.embedding is created.embedding
    assert len(provider.inputs) == 2
    session.commit.assert_not_called()


@pytest.fixture
def route_setup() -> tuple[TestClient, Mock, FakeProvider, Memory]:
    session = Mock()
    provider = FakeProvider()
    memory = stored_memory()
    application = create_app()
    application.dependency_overrides[get_db_session] = lambda: session
    application.dependency_overrides[provider_dependency] = lambda: provider
    return TestClient(application), session, provider, memory


def test_route_commits_once_and_never_returns_vector(
    monkeypatch: pytest.MonkeyPatch,
    route_setup: tuple[TestClient, Mock, FakeProvider, Memory],
) -> None:
    client, session, _, memory = route_setup
    row = MemoryEmbedding(
        id=uuid.uuid4(),
        memory_id=memory.id,
        provider="fake",
        model="fixed-model",
        dimensions=1536,
        embedding=[0.1] * 1536,
        input_hash="a" * 64,
        embedded_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    monkeypatch.setattr(
        "app.api.routes.memories.memory_repository.get_memory",
        Mock(return_value=memory),
    )
    monkeypatch.setattr(
        "app.api.routes.memories.embedding_repository.generate_memory_embedding",
        Mock(return_value=repository.GenerationResult(row, "created")),
    )
    response = client.post(f"/memories/{memory.id}/embedding")
    assert response.status_code == 200
    assert response.json()["generation_status"] == "created"
    assert "embedding" not in response.json()
    session.commit.assert_called_once_with()


def test_route_exact_errors_and_rollbacks(
    monkeypatch: pytest.MonkeyPatch,
    route_setup: tuple[TestClient, Mock, FakeProvider, Memory],
) -> None:
    client, session, _, memory = route_setup
    get_memory = Mock(return_value=None)
    monkeypatch.setattr(
        "app.api.routes.memories.memory_repository.get_memory", get_memory
    )
    response = client.post(f"/memories/{memory.id}/embedding")
    assert response.status_code == 404
    assert response.json() == {"detail": "memory not found"}

    get_memory.return_value = memory
    for error, expected in [
        (
            ProviderRequestError("secret provider detail"),
            (502, "embedding provider failed"),
        ),
        (
            InvalidEmbeddingResponseError("secret vector"),
            (502, "invalid embedding response"),
        ),
        (
            OperationalError("secret SQL", {}, Exception("password=secret")),
            (503, "database unavailable"),
        ),
    ]:
        monkeypatch.setattr(
            "app.api.routes.memories.embedding_repository.generate_memory_embedding",
            Mock(side_effect=error),
        )
        response = client.post(f"/memories/{memory.id}/embedding")
        assert (response.status_code, response.json()["detail"]) == expected
        assert "secret" not in response.text
    assert session.rollback.call_count == 4


def test_missing_key_is_generic_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()
    response = TestClient(create_app()).post(f"/memories/{uuid.uuid4()}/embedding")
    assert response.status_code == 503
    assert response.json() == {"detail": "embedding provider unavailable"}
    get_settings.cache_clear()
