"""PostgreSQL verification for the explicit embedding endpoint."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.routes.memories import provider_dependency
from app.db.session import get_engine
from app.main import create_app
from app.models import Memory, MemoryEmbedding
from tests.integration.conftest import verify_connected_test_database


class FixedProvider:
    name = "fake"
    model = "fixed-1536"
    dimensions = 1536

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, text: str) -> list[float]:
        self.calls += 1
        return [0.125] * 1536


@pytest.fixture
def embedding_client(
    migrated_test_database: None, test_database_url: str
) -> Generator[tuple[TestClient, FixedProvider], None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.commit()
    provider = FixedProvider()
    application = create_app()
    application.dependency_overrides[provider_dependency] = lambda: provider
    yield TestClient(application), provider
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.commit()


def test_endpoint_create_update_unchanged_and_cascade(
    embedding_client: tuple[TestClient, FixedProvider],
) -> None:
    client, provider = embedding_client
    created_memory = client.post(
        "/memories",
        json={
            "title": "Title",
            "summary": "Summary",
            "content": "Body",
            "source": "legacy",
        },
    ).json()
    memory_id = uuid.UUID(created_memory["id"])
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(MemoryEmbedding)) == 0

    created = client.post(f"/memories/{memory_id}/embedding")
    assert created.status_code == 200
    assert created.json()["generation_status"] == "created"
    assert "embedding" not in created.json()
    row_id = created.json()["id"]
    first_hash = created.json()["input_hash"]
    unchanged = client.post(f"/memories/{memory_id}/embedding")
    assert unchanged.json()["generation_status"] == "unchanged"
    assert unchanged.json()["id"] == row_id
    assert provider.calls == 1

    with Session(get_engine()) as session:
        memory = session.get(Memory, memory_id)
        assert memory is not None
        memory.importance = 0.9
        memory.confidence = 0.8
        memory.status = "archived"
        session.commit()
    still_unchanged = client.post(f"/memories/{memory_id}/embedding")
    assert still_unchanged.json()["generation_status"] == "unchanged"
    assert still_unchanged.json()["input_hash"] == first_hash

    with Session(get_engine()) as session:
        memory = session.get(Memory, memory_id)
        assert memory is not None
        memory.content = "Changed body"
        session.commit()
    updated = client.post(f"/memories/{memory_id}/embedding")
    assert updated.json()["generation_status"] == "updated"
    assert updated.json()["id"] == row_id
    assert updated.json()["input_hash"] != first_hash
    assert provider.calls == 2
    with Session(get_engine()) as session:
        row = session.scalar(
            select(MemoryEmbedding).where(MemoryEmbedding.memory_id == memory_id)
        )
        assert row is not None
        assert len(row.embedding) == 1536
        assert session.scalar(select(func.count()).select_from(MemoryEmbedding)) == 1
        memory = session.get(Memory, memory_id)
        assert memory is not None
        session.delete(memory)
        session.commit()
        assert session.scalar(select(func.count()).select_from(MemoryEmbedding)) == 0
