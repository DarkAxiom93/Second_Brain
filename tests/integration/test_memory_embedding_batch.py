"""PostgreSQL coverage for explicit batch Memory embedding generation."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.routes.memory_embedding_batches import (
    configured_embedding_identity,
    provider_resolver,
)
from app.db.session import get_engine
from app.main import create_app
from app.models import Memory, MemoryEmbedding, Project
from app.repositories.memory_embeddings import (
    canonical_input_hash,
    canonical_memory_text,
)
from tests.integration.conftest import verify_connected_test_database


class BatchProvider:
    name = "fake"
    model = "fixed-1536"
    dimensions = 1536

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, text: str) -> list[float]:
        return [0.25] * self.dimensions

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [
            [float(index + 1) / 10] * self.dimensions for index in range(len(texts))
        ]


@pytest.fixture
def batch_client(
    migrated_test_database: None, test_database_url: str
) -> Generator[tuple[TestClient, BatchProvider], None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()
    provider = BatchProvider()
    application = create_app()
    application.dependency_overrides[provider_resolver] = lambda: lambda: provider
    application.dependency_overrides[configured_embedding_identity] = lambda: (
        provider.name,
        provider.model,
        provider.dimensions,
    )
    yield TestClient(application), provider
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()


def test_scopes_order_limit_active_missing_and_metadata(
    batch_client: tuple[TestClient, BatchProvider],
) -> None:
    client, provider = batch_client
    base = datetime.now(UTC) - timedelta(days=1)
    with Session(get_engine()) as session:
        project = Project(name="Batch project")
        session.add(project)
        session.flush()
        rows = [
            Memory(
                id=uuid.UUID(int=3),
                project_id=project.id,
                content="third",
                created_at=base,
            ),
            Memory(
                id=uuid.UUID(int=1),
                project_id=project.id,
                content="first",
                created_at=base,
            ),
            Memory(
                id=uuid.UUID(int=2),
                project_id=None,
                content="unassigned",
                created_at=base,
            ),
            Memory(
                id=uuid.UUID(int=4),
                project_id=project.id,
                content="inactive",
                status="archived",
                created_at=base,
            ),
        ]
        session.add_all(rows)
        session.flush()
        existing = MemoryEmbedding(
            memory_id=rows[0].id,
            provider="old",
            model="old-model",
            dimensions=1536,
            embedding=[0.9] * 1536,
            input_hash="a" * 64,
            embedded_at=base,
        )
        session.add(existing)
        session.commit()
        project_id = project.id
        first_id = rows[1].id
        unassigned_id = rows[2].id
        existing_id = existing.id

    response = client.post(
        "/memory-embeddings/batch",
        json={"scope": "all", "limit": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert [item["memory_id"] for item in body["items"]] == [
        str(first_id),
        str(unassigned_id),
    ]
    assert body["created_count"] == 2
    assert body["unchanged_count"] == body["skipped_count"] == 0
    assert len(provider.calls) == 1
    with Session(get_engine()) as session:
        created = session.scalars(
            select(MemoryEmbedding).where(MemoryEmbedding.provider == "fake")
        ).all()
        assert len(created) == 2
        memories = {row.id: row for row in session.scalars(select(Memory))}
        for row in created:
            assert row.model == "fixed-1536" and row.dimensions == 1536
            assert row.input_hash == canonical_input_hash(
                canonical_memory_text(memories[row.memory_id])
            )
        old = session.get(MemoryEmbedding, existing_id)
        assert old is not None and old.provider == "old"

    empty = client.post(
        "/memory-embeddings/batch",
        json={"scope": "project", "project_id": str(uuid.uuid4())},
    )
    assert empty.status_code == 200 and empty.json()["batch_status"] == "empty"
    assert len(provider.calls) == 1

    unassigned = client.post("/memory-embeddings/batch", json={"scope": "unassigned"})
    assert (
        unassigned.status_code == 200 and unassigned.json()["batch_status"] == "empty"
    )

    project_result = client.post(
        "/memory-embeddings/batch",
        json={"scope": "project", "project_id": str(project_id)},
    )
    assert project_result.status_code == 200
    assert project_result.json()["batch_status"] == "empty"


def test_reembed_stale_and_forced_all_preserve_identity(
    batch_client: tuple[TestClient, BatchProvider],
) -> None:
    client, provider = batch_client
    base = datetime.now(UTC) - timedelta(days=1)
    with Session(get_engine()) as session:
        project = Project(name="Re-embedding project")
        session.add(project)
        session.flush()
        stale = Memory(project_id=project.id, content="stale", created_at=base)
        current = Memory(
            project_id=project.id,
            content="current",
            created_at=base + timedelta(seconds=1),
        )
        missing = Memory(project_id=project.id, content="missing")
        inactive = Memory(project_id=project.id, content="inactive", status="archived")
        session.add_all([stale, current, missing, inactive])
        session.flush()
        stale_embedding = MemoryEmbedding(
            memory_id=stale.id,
            provider="old",
            model="old",
            dimensions=1536,
            embedding=[0.9] * 1536,
            input_hash="a" * 64,
            embedded_at=base,
            created_at=base,
        )
        current_embedding = MemoryEmbedding(
            memory_id=current.id,
            provider=provider.name,
            model=provider.model,
            dimensions=provider.dimensions,
            embedding=[0.8] * 1536,
            input_hash=canonical_input_hash(canonical_memory_text(current)),
            embedded_at=base,
            created_at=base,
        )
        session.add_all([stale_embedding, current_embedding])
        session.commit()
        project_id = project.id
        stale_id = stale.id
        embedding_id = stale_embedding.id
        created_at = stale_embedding.created_at

    response = client.post(
        "/memory-embeddings/reembed",
        json={
            "scope": "project",
            "project_id": str(project_id),
            "selection": "stale",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["selected_count"] == body["updated_count"] == 1
    assert body["items"][0]["memory_id"] == str(stale_id)
    assert body["items"][0]["previous_embedding"]["provider"] == "old"
    assert body["items"][0]["current_embedding"]["provider"] == provider.name
    assert len(provider.calls) == 1
    with Session(get_engine()) as session:
        replaced = session.get(MemoryEmbedding, embedding_id)
        assert replaced is not None
        assert replaced.id == embedding_id and replaced.created_at == created_at
        assert replaced.input_hash == canonical_input_hash(
            canonical_memory_text(session.get(Memory, stale_id))
        )

    forced = client.post(
        "/memory-embeddings/reembed",
        json={
            "scope": "project",
            "project_id": str(project_id),
            "selection": "all",
            "limit": 1,
        },
    )
    assert forced.status_code == 200
    assert forced.json()["selected_count"] == forced.json()["unchanged_count"] == 1
    assert forced.json()["updated_count"] == 0
    assert len(provider.calls) == 2
